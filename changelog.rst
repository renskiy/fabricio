Changelog
=========

Release 0.3.2
-------------

- Change: ``PostgresqlContainer`` doesn't contain ``PostgresqlBackupMixin`` now
- Change: reworked Docker container options, now they provided as kwargs

Release 0.3.1
-------------

- Change: removed deprecated ``CronContainer``
- Change: removed deprecated ``utils.yes()``
- Fix: fixed Fabric's ``serial`` and ``parallel`` decorators usage within ``Tasks``
- Change: ``PostgresqlContainer``: deprecated 'postgresql_conf', 'pg_hba_conf' and 'data' properties in favour of new ones
- Change: ``PostgresqlBackupMixin``: deprecated 'db_backup_folder' and 'db_backup_name' properties in favour of new ones
- Change: ``PostgresqlBackupMixin``: removed ``db_backup_enabled`` flag
- Enhancement: ``fabricio.run()``: added 'use_cache=False' option which enables shared cache incapsulated within single infrastructure
- Enhancement: ``PostgresqlBackupMixin``: 'backup' and 'restore' cache result per infrastructure

Release 0.3
-----------

- Change: ``PostgresqlBackupMixin``: do actual backup only if ``db_backup_enabled`` is True
- Change: modified ``DockerTasks`` commands params order: force, tag, registry => tag, registry, force(`#52`_)
- Change: ``DockerTasks``: 'revert' command was removed from the list of available commands in favour of 'rollback'
- Change: ``tasks.infrastructure`` decorator does not require special environ variable to be autoconfirmed, instead special command '<infrastructure>.confirm' can be used for this purpose

.. _#52: https://github.com/renskiy/fabricio/issues/52

Release 0.2.17
--------------

- Fix: fixed bug when Container.update() changed container name

Release 0.2.16
--------------

- Fix: fixed Django migrations plan
- Fix: fixed Django migrations change detection

Release 0.2.14
--------------

- Enhancement: ``docker.Container.update()`` forces starting container if no changes detected
- Enhancement: ``apps.python.django.DjangoContainer.migrate()`` does not run ``migrate`` if actually no changes detected
- Enhancement: ``apps.python.django.DjangoContainer.migrate()`` calls ``backup()`` before applying migrations
- Change: ``tasks.DockerTasks.deploy()`` does not run ``backup`` task by default
- Enhancement: implemented ``apps.db.postgres.PostgresqlContainer.backup()`` and ``apps.db.postgres.PostgresqlContainer.restore()`` (`#17`_)
- Enhancement: Fabric's ``remote_tunnel`` has been muzzled and ``tasks.DockerTasks.pull()`` output enabled instead (`#42`_)

.. _#17: https://github.com/renskiy/fabricio/issues/17
.. _#42: https://github.com/renskiy/fabricio/issues/42

Release 0.2.13
--------------

- Enhancement: ``tasks.BuildDockerTasks.prepare()`` always uses ``docker build``'s --pull option

Release 0.2.12
--------------

- Fix: fixed Fabric's --display option (`#33`_)
- Enhancement: skip tasks which require host where last is not provided (`#45`_)

.. _#33: https://github.com/renskiy/fabricio/issues/33
.. _#45: https://github.com/renskiy/fabricio/issues/45
