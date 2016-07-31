Changelog
=========

Release 0.2.14
--------------

- Enhancement: ``docker.Container.update()`` forces starting container if no changes detected
- Enhancement: ``apps.python.django.DjangoContainer.migrate()`` does not run ``migrate`` if actually no changes detected
- Enhancement: ``apps.python.django.DjangoContainer.migrate()`` calls ``backup()`` before applying migrations
- Change: ``tasks.DockerTasks.deploy()`` does not run ``backup`` task by default
- Enhancement: implemented ``apps.db.postgres.PostgresqlContainer.backup()`` and ``apps.db.postgres.PostgresqlContainer.restore()`` (`#17`_)

.. _#17: https://github.com/renskiy/fabricio/issues/17

Release 0.2.13
--------------

- Enhancement: ``tasks.BuildDockerTasks.prepare()`` always uses ``docker build``'s --pull option

Release 0.2.12
--------------

- Fix: Fixed Fabric's --display option (`#33`_)
- Enhancement: Skip tasks which require host where last is not provided (`#45`_)

.. _#33: https://github.com/renskiy/fabricio/issues/33
.. _#45: https://github.com/renskiy/fabricio/issues/45
