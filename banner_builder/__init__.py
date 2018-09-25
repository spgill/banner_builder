# stdlib imports
import io
import json
import os
import sqlite3
import struct
import tempfile
import zipfile

# vendor imports
from PIL import Image, ImageOps
import requests

# local imports


# Constants
ROOT = 'https://bungie.net'
APIKEY = os.environ.get('BUNGIE_API_KEY', None)
MODIFIER = 4294967296

# Check that the apikey was passed
if APIKEY is None:
    raise RuntimeError(
        'Please place your api key in the `BUNGIE_API_KEY` environment var'
    )


def cast(n):
    return struct.unpack('i', struct.pack('I', n))[0]


def jsonForId(cursor, tableName, id):
    return json.loads(
        cursor.execute(
            f'SELECT json FROM {tableName} WHERE id={cast(id)}'
        ).fetchone()[0]
    )


def colorToTuple(color):
    return (
        color['red'],
        color['green'],
        color['blue'],
    )


def imageWithColor(url, color):
    # Turn the color dictionary into a tuple
    colorTuple = colorToTuple(color)

    # Fetch the image from the URL
    src = Image.open(
        requests.get(
            url=ROOT + url,
            stream=True
        ).raw
    )

    # Split off the alpha channel
    alpha = src.split()[3]

    # Colorize the source image
    gray = ImageOps.grayscale(src)
    result = ImageOps.colorize(gray, (0, 0, 0, 0), colorTuple)

    # Reintegrate and return
    result.putalpha(alpha)
    return result


def parse(clanId):
    """Parse and assemble a banner for clan with ID `clanId`"""
    # Simple reusable headers objects
    headers = {
        'X-Api-Key': APIKEY
    }

    # First, fetch the manifest
    manifest = requests.get(
        url=ROOT + '/Platform/Destiny2/Manifest',
        headers=headers,
    ).json()

    # Hash the banner database path
    dbPath = manifest['Response']['mobileClanBannerDatabasePath']

    # Fetch the compressed database file
    dbRequest = requests.get(
        url=ROOT + dbPath,
        headers=headers,
    )

    # Decompress it
    dbBuffer = io.BytesIO(dbRequest.content)
    dbArchive = zipfile.ZipFile(dbBuffer)
    dbFileBuffer = dbArchive.open(dbArchive.infolist()[0])

    # Transfer the decompressed data into a temporary file
    dbFile = tempfile.NamedTemporaryFile('wb', delete=False)
    dbFile.write(dbFileBuffer.read())
    dbFile.close()

    # Connect to the database file
    dbConnection = sqlite3.connect(dbFile.name)
    dbCursor = dbConnection.cursor()

    # Time to get the clan data
    clanData = requests.get(
        url=ROOT + f'/Platform/GroupV2/{clanId}/',
        headers=headers,
    ).json()
    bannerData = clanData['Response']['detail']['clanInfo']['clanBannerData']

    # We use the gonfalon color as the background color
    canvasColor = jsonForId(
        dbCursor,
        'GonfalonColors',
        bannerData['gonfalonColorId']
    )

    # Create the image canvas to draw on
    canvas = Image.new(
        mode='RGBA',
        size=(402, 594),
        color=colorToTuple(canvasColor),
    )

    # Get the gonfalon detail
    gonfalonDetailEntry = jsonForId(
        dbCursor,
        'GonfalonDetails',
        bannerData['gonfalonDetailId'],
    )

    # Paste the gonfalon in
    gonfalonFg = imageWithColor(
        gonfalonDetailEntry['foregroundImagePath'],
        jsonForId(
            dbCursor,
            'GonfalonDetailColors',
            bannerData['gonfalonDetailColorId']
        ),
    )
    canvas = Image.alpha_composite(canvas, gonfalonFg)

    # Get the decal
    decalEntry = jsonForId(
        dbCursor,
        'Decals',
        bannerData['decalId'],
    )

    # Paste the background decal in
    decalBg = imageWithColor(
        decalEntry['backgroundImagePath'],
        jsonForId(
            dbCursor,
            'DecalSecondaryColors',
            bannerData['decalBackgroundColorId']
        ),
    )
    canvas = Image.alpha_composite(canvas, decalBg)

    # Paste the foreground decal in
    decalFg = imageWithColor(
        decalEntry['foregroundImagePath'],
        jsonForId(
            dbCursor,
            'DecalPrimaryColors',
            bannerData['decalColorId']
        ),
    )
    canvas = Image.alpha_composite(canvas, decalFg)

    # Finally, close the database connection and delete the file
    dbConnection.close()
    os.remove(dbFile.name)

    # Return the canvas image
    return canvas
