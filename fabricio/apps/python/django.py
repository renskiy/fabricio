import itertools

from fabricio import docker, utils


class Migration(str):

    def __init__(self, *args, **kwargs):
        super(Migration, self).__init__(*args, **kwargs)
        self.app, _, self.name = self.partition('.')


class DjangoMixin(docker.BaseService):
    """
    Be sure you use proper Dockerfile's WORKDIR directive
    (or another alternative) which points to the directory where
    manage.py placed
    """

    @utils.once_per_command
    def migrate(self, tag=None, registry=None):
        self.image[registry:tag].run(
            'python manage.py migrate --noinput',
            quiet=False,
            options=self.safe_options,
        )

    @staticmethod
    def _get_parent_migration(migration, migrations):
        migrations = iter(migrations)
        any(migration == m for m in migrations)  # skip later migrations
        for parent_migration in migrations:
            if migration.app == parent_migration.app:
                return parent_migration
        return Migration(migration.app + '.zero')

    def get_revert_migrations(self, current_migrations, backup_migrations):
        current_migrations, all_migrations = itertools.tee(reversed(map(
            Migration,
            current_migrations.splitlines(),
        )))
        all_migrations = list(all_migrations)

        backup_migrations = reversed(map(
            Migration,
            backup_migrations.splitlines(),
        ))

        revert_migrations = utils.OrderedDict()

        while True:
            backup_migration = next(backup_migrations, None)
            for current_migration in current_migrations:
                if current_migration == backup_migration:
                    break
                revert_migrations[current_migration.app] = self._get_parent_migration(
                    current_migration,
                    migrations=all_migrations,
                )

            if backup_migration is None:
                return revert_migrations.values()

    @utils.once_per_command
    def migrate_back(self):
        migrations_command = 'python manage.py showmigrations --plan ' \
                             '| egrep "^\[X\]" ' \
                             '| awk "{print \$2}"'
        image = self.image
        options = self.safe_options

        with utils.patch(self, 'info', self.info, force_delete=True):
            current_migrations = image.run(
                migrations_command,
                options=options,
            )
            backup_migrations = self.get_backup_version().image.run(
                migrations_command,
                options=options,
            )

            for migration in self.get_revert_migrations(
                current_migrations,
                backup_migrations,
            ):
                command = (
                    'python manage.py migrate --no-input {app} {migration}'
                ).format(
                    app=migration.app,
                    migration=migration.name,
                )
                image.run(command, quiet=False, options=options)


class DjangoContainer(docker.Container, DjangoMixin):
    pass


class DjangoService(docker.Service, DjangoMixin):
    pass
