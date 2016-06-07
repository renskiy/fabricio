from fabricio import docker


class CronContainer(docker.Container):
    """
    This class designed to use with Docker containers created
    from images which inherit for example this image:
    https://hub.docker.com/r/renskiy/cron/
    """

    cmd = '/bin/bash -c "cron && tail -f /var/log/cron.log"'

    def before_stop(self):
        self.execute('killall -HUP tail', ignore_errors=True)

    def stop(self, *args, **kwargs):
        self.before_stop()
        super(CronContainer, self).stop(*args, **kwargs)

    def restart(self, *args, **kwargs):
        self.before_stop()
        super(CronContainer, self).restart(*args, **kwargs)
