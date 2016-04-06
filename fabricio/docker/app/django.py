from fabric import api as fab

from fabricio.docker.container import Container


class Django(Container):

    @fab.runs_once
    def apply_migrations(self):
        self.fork(temporary=True).execute('manage.py migrate --noinput')

    def upgrade(self):
        self.apply_migrations()
        super(Django, self).upgrade()

    @fab.runs_once
    def squash_migrations(self):
        pass  # TODO

    def fallback(self):
        self.squash_migrations()
        super(Django, self).fallback()
