# stdlib imports

# vendor imports
import click

# local imports
import banner_builder


@click.command()
@click.argument('CLANID', type=int)
@click.argument('OUTPUT', type=click.Path())
def cli(clanid, output):
    image = banner_builder.parse(clanid)
    image.save(output)


if __name__ == '__main__':
    cli()
