import argparse


class SucceededResult(str):

    succeeded = True

    failed = False


class FailedResult(str):

    succeeded = False

    failed = True

docker_run_args_parser = argparse.ArgumentParser(argument_default=argparse.SUPPRESS)
docker_run_args_parser.add_argument('executable', nargs=1)
docker_run_args_parser.add_argument('run_or_create', nargs=1)
docker_run_args_parser.add_argument('--user')
docker_run_args_parser.add_argument('--publish', action='append')
docker_run_args_parser.add_argument('--env', action='append')
docker_run_args_parser.add_argument('--volume', action='append')
docker_run_args_parser.add_argument('--link', action='append')
docker_run_args_parser.add_argument('--label', action='append')
docker_run_args_parser.add_argument('--add-host', action='append', dest='add-host')
docker_run_args_parser.add_argument('--net')
docker_run_args_parser.add_argument('--network')
docker_run_args_parser.add_argument('--mount')
docker_run_args_parser.add_argument('--restart')
docker_run_args_parser.add_argument('--stop-signal', dest='stop-signal')
docker_run_args_parser.add_argument('--detach', action='store_true')
docker_run_args_parser.add_argument('--tty', action='store_true')
docker_run_args_parser.add_argument('--interactive', action='store_true')
docker_run_args_parser.add_argument('--rm', action='store_true')
docker_run_args_parser.add_argument('--name')
docker_run_args_parser.add_argument('--custom-option', dest='custom-option')
docker_run_args_parser.add_argument('image')
docker_run_args_parser.add_argument('command', nargs=argparse.REMAINDER)

args_parser = argparse.ArgumentParser(argument_default=argparse.SUPPRESS)
args_parser.add_argument('args', nargs=argparse.REMAINDER)

# TODO use args_parser instead
docker_inspect_args_parser = argparse.ArgumentParser(argument_default=argparse.SUPPRESS)
docker_inspect_args_parser.add_argument('executable', nargs=2)
docker_inspect_args_parser.add_argument('--type')
docker_inspect_args_parser.add_argument('image_or_container')

# TODO use args_parser instead
docker_entity_inspect_args_parser = argparse.ArgumentParser(argument_default=argparse.SUPPRESS)
docker_entity_inspect_args_parser.add_argument('executable', nargs=3)
docker_entity_inspect_args_parser.add_argument('--format')
docker_entity_inspect_args_parser.add_argument('service')

docker_service_update_args_parser = argparse.ArgumentParser(argument_default=argparse.SUPPRESS)
docker_service_update_args_parser.add_argument('executable', nargs=3)
docker_service_update_args_parser.add_argument('--env-add', dest='env-add', action='append')
docker_service_update_args_parser.add_argument('--env-rm', dest='env-rm', action='append')
docker_service_update_args_parser.add_argument('--image')
docker_service_update_args_parser.add_argument('--mount-add', dest='mount-add', action='append')
docker_service_update_args_parser.add_argument('--mount-rm', dest='mount-rm', action='append')
docker_service_update_args_parser.add_argument('--name')
docker_service_update_args_parser.add_argument('--publish-add', dest='publish-add', action='append')
docker_service_update_args_parser.add_argument('--publish-rm', dest='publish-rm', action='append')
docker_service_update_args_parser.add_argument('--label-add', dest='label-add', action='append')
docker_service_update_args_parser.add_argument('--label-rm', dest='label-rm', action='append')
docker_service_update_args_parser.add_argument('--constraint-add', dest='constraint-add', action='append')
docker_service_update_args_parser.add_argument('--constraint-rm', dest='constraint-rm', action='append')
docker_service_update_args_parser.add_argument('--container-label-add', dest='container-label-add', action='append')
docker_service_update_args_parser.add_argument('--container-label-rm', dest='container-label-rm', action='append')
docker_service_update_args_parser.add_argument('--network-add', dest='network-add', action='append')
docker_service_update_args_parser.add_argument('--network-rm', dest='network-rm', action='append')
docker_service_update_args_parser.add_argument('--replicas')
docker_service_update_args_parser.add_argument('--restart-condition', dest='restart-condition')
docker_service_update_args_parser.add_argument('--user')
docker_service_update_args_parser.add_argument('--stop-grace-period', dest='stop-grace-period')
docker_service_update_args_parser.add_argument('--args')
docker_service_update_args_parser.add_argument('--custom_option')
docker_service_update_args_parser.add_argument('service')

docker_service_create_args_parser = argparse.ArgumentParser(argument_default=argparse.SUPPRESS)
docker_service_create_args_parser.add_argument('executable', nargs=3)
docker_service_create_args_parser.add_argument('--env', action='append')
docker_service_create_args_parser.add_argument('--mount', action='append')
docker_service_create_args_parser.add_argument('--name')
docker_service_create_args_parser.add_argument('--publish', action='append')
docker_service_create_args_parser.add_argument('--label', action='append')
docker_service_create_args_parser.add_argument('--constraint', action='append')
docker_service_create_args_parser.add_argument('--container-label', dest='container-label', action='append')
docker_service_create_args_parser.add_argument('--replicas')
docker_service_create_args_parser.add_argument('--restart-condition', dest='restart-condition')
docker_service_create_args_parser.add_argument('--user')
docker_service_create_args_parser.add_argument('--network')
docker_service_create_args_parser.add_argument('--mode')
docker_service_create_args_parser.add_argument('--stop-grace-period', dest='stop-grace-period')
docker_service_create_args_parser.add_argument('--custom_option')
docker_service_create_args_parser.add_argument('image', nargs=1)
docker_service_create_args_parser.add_argument('args', nargs=argparse.REMAINDER)

docker_build_args_parser = argparse.ArgumentParser(argument_default=argparse.SUPPRESS)
docker_build_args_parser.add_argument('executable', nargs=2)
docker_build_args_parser.add_argument('--tag')
docker_build_args_parser.add_argument('--no-cache', type=int, dest='no-cache')
docker_build_args_parser.add_argument('--pull', nargs='?', const=True, type=int)
docker_build_args_parser.add_argument('--force-rm', nargs='?', const=True, type=int, dest='force-rm')
docker_build_args_parser.add_argument('--custom')
docker_build_args_parser.add_argument('--custom-bool', nargs='?', const=True, type=int, dest='custom-bool')
docker_build_args_parser.add_argument('path')
