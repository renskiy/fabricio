from fabric import api as fab

from fabricio import docker


class Django(docker.Container):

    @fab.runs_once
    def apply_migrations(self):
        self.fork(temporary=True).execute('manage.py migrate --noinput')

    def update(self, force=False, tag=None):
        self.apply_migrations()
        super(Django, self).update(force=force, tag=tag)

    @fab.runs_once
    def squash_migrations(self):
        migrations_list = 'manage.py showmigrations --plan | egrep "^\[X\]"'

        current_migrations = self.fork(
            temporary=True,
        ).execute(migrations_list).stdout

        fallback_migrations = self.fork(
            image=self.get_backup_container().image.id,
            temporary=True,
        ).execute(migrations_list).stdout
        # TODO finish implementation

    def revert(self):
        self.squash_migrations()
        super(Django, self).revert()
