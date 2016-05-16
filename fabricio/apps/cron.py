from fabricio import docker


class Cron(docker.Container):

    cmd = 'cron && tail -f /var/log/cron.log'

    def before_stop(self):
        self.execute('killall -HUP tail')

    def stop(self, *args, **kwargs):
        self.before_stop()
        super(Cron, self).stop(*args, **kwargs)

    def restart(self, *args, **kwargs):
        self.before_stop()
        super(Cron, self).restart(*args, **kwargs)
