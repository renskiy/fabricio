import itertools

from six.moves import map, filter

from fabricio import docker, utils


class Migration(str):

    def __init__(self, *args, **kwargs):
        super(Migration, self).__init__(**kwargs)
        self.app, _, self.name = self.partition('.')


class DjangoMixin(docker.BaseService):
    """
    Be sure you use proper Dockerfile's WORKDIR directive
    (or another alternative) which points to the directory where
    manage.py placed
    """

    @staticmethod
    def _migrate(image, options):
        image.run(
            'python manage.py migrate --noinput',
            quiet=False,
            options=options,
        )

    @utils.once_per_command
    def migrate(self, tag=None, registry=None, account=None):
        self._migrate(
            image=self.image[registry:tag:account],
            options=self.safe_options,
        )

    @staticmethod
    def _get_parent_migration(migration, migrations):
        migrations = iter(migrations)
        any(map(migration.__eq__, migrations))  # skip later migrations
        for parent_migration in migrations:
            if migration.app == parent_migration.app:
                return parent_migration
        return Migration(migration.app + '.zero')

    def get_revert_migrations(self, current_migrations, backup_migrations):
        current_migrations, all_migrations = itertools.tee(reversed(list(map(
            Migration,
            filter(None, current_migrations.splitlines()),
        ))))
        all_migrations = utils.OrderedSet(all_migrations)

        backup_migrations = reversed(list(map(
            Migration,
            filter(None, backup_migrations.splitlines()),
        )))

        revert_migrations = utils.OrderedDict()

        while True:
            while True:
                backup_migration = next(backup_migrations, None)
                if not backup_migration or backup_migration in all_migrations:
                    break
            for current_migration in current_migrations:
                if current_migration == backup_migration:
                    break
                revert_migration = self._get_parent_migration(
                    current_migration,
                    migrations=all_migrations,
                )
                revert_migrations[current_migration.app] = revert_migration

            if backup_migration is None:
                return revert_migrations.values()

    @utils.once_per_command
    def migrate_back(self):
        migrations_command = (
            'python manage.py showmigrations --plan '  # execute plan
            '| egrep \'^\\[X\\]\' '  # show only applied migrations
            '| awk \'{print $2}\' '  # take migration name
            '&& test ${PIPESTATUS[0]} -eq 0'  # fail if couldn't execute plan
        )
        image = self.image
        options = self.safe_options

        with utils.patch(self, 'info', self.info, force_delete=True):
            current_migrations = image.run(
                migrations_command,
                options=options,
            )
            backup = self.get_backup_version()
            with utils.patch(backup, 'info', backup.info, force_delete=True):
                backup_migrations = backup.image.run(
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

                self._migrate(backup.image, options)


class DjangoContainer(docker.Container, DjangoMixin):
    pass


class DjangoService(docker.Service, DjangoMixin):
    pass
