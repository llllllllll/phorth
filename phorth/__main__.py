import click

from phorth.runner import run_phorth


@click.command()
@click.option(
    '-s',
    '--stack-size',
    default=30000,
    type=int,
    help='The size the the stack for the phorth program.',
)
@click.option(
    '-m',
    '--memory',
    default=65535,
    type=int,
    help='The size the the memory space for the phorth program.',
)
def main(memory, stack_size):
    run_phorth(stack_size, memory)


if __name__ == '__main__':
    main()
