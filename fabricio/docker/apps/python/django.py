from fabric import api as fab

from fabricio.docker.containers import Container


class Django(Container):

    @fab.runs_once
    def apply_migrations(self):
        self.fork(temporary=True).execute('manage.py migrate --noinput')

    def upgrade(self, force=False):
        self.apply_migrations()
        super(Django, self).upgrade(force=force)

    @fab.runs_once
    def squash_migrations(self):
        migrations_list = 'manage.py showmigrations --plan | egrep "^\[X\]"'

        current_migrations = self.fork(
            temporary=True,
        ).execute(migrations_list).stdout

        fallback_migrations = self.fork(
            image=self.fallback_container.image_id,
            temporary=True,
        ).execute(migrations_list).stdout

    def fallback(self):
        self.squash_migrations()
        super(Django, self).fallback()
