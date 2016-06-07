import collections
import itertools

from cached_property import cached_property
from fabric import api as fab

from fabricio import docker


class Migration(str):

    def split_migration(self):
        app, _, name = self.partition('.')
        return app, name

    @cached_property
    def app(self):
        app, self.name = self.split_migration()
        return app

    @cached_property
    def name(self):
        self.app, name = self.split_migration()
        return name


class DjangoContainer(docker.Container):
    """
    Be sure you use proper Dockerfile's WORKDIR directive
    (or another alternative) which points to the directory where
    manage.py placed
    """

    @property
    def migration_options(self):
        return dict(
            user=self.user,
            env=self.env,
            volumes=self.volumes,
            links=self.links,
            hosts=self.hosts,
            network=self.network,
        )

    @fab.runs_once
    def apply_migrations(self, tag=None):
        self.__class__.image[tag].run(
            'python manage.py migrate --noinput',
            **self.migration_options
        )

    def update(self, force=False, tag=None):
        self.apply_migrations(tag=tag)
        return super(DjangoContainer, self).update(force=force, tag=tag)

    @staticmethod
    def _get_parent_migration(migration, migrations):
        migrations = iter(migrations)
        list(iter(migrations.next, migration))  # skip children migrations
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

        revert_migrations = collections.OrderedDict()

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

    @fab.runs_once
    def revert_migrations(self):
        migrations_cmd = 'python manage.py showmigrations --plan | egrep "^\[X\]" | awk {print \$2}'

        try:
            current_migrations = self.image.run(
                cmd=migrations_cmd,
                **self.migration_options
            )
            backup_migrations = self.get_backup_container().image.run(
                cmd=migrations_cmd,
                **self.migration_options
            )
        except RuntimeError:  # either current or backup container not found
            return

        revert_migrations = self.get_revert_migrations(
            current_migrations,
            backup_migrations,
        )
        for migration in revert_migrations:
            cmd = 'python manage.py migrate --no-input {app} {migration}'.format(
                app=migration.app,
                migration=migration.name,
            )
            self.image.run(cmd=cmd, **self.migration_options)  # TODO logging

    def revert(self):
        self.revert_migrations()
        super(DjangoContainer, self).revert()
