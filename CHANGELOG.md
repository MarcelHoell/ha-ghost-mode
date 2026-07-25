# Changelog

## [0.10.0](https://github.com/MarcelHoell/ha-ghost-mode/compare/v0.9.0...v0.10.0) (2026-07-25)


### Features

* add a force switch that overrides the alarm ([cc04271](https://github.com/MarcelHoell/ha-ghost-mode/commit/cc04271fad8456a279706560c980148602c4006f))
* report whether replay is actually performing ([710212f](https://github.com/MarcelHoell/ha-ghost-mode/commit/710212fdd7d93da2bc69f7906e34691e51797f7f))


### Bug Fixes

* use the entity id Home Assistant actually generates ([36c7914](https://github.com/MarcelHoell/ha-ghost-mode/commit/36c7914f0d77f0d4b384596109ace27817acbdb2))

## [0.9.0](https://github.com/MarcelHoell/ha-ghost-mode/compare/v0.8.1...v0.9.0) (2026-07-25)


### Features

* replay the learned rhythm while the house is empty ([0e319b4](https://github.com/MarcelHoell/ha-ghost-mode/commit/0e319b447d8b041fe9df54ac275ea0600e55e757))


### Bug Fixes

* do not schedule replay from an executor thread ([431f62f](https://github.com/MarcelHoell/ha-ghost-mode/commit/431f62f47d60a8cc64b47c653def56ba07af1331))
* prune replayed days against today, not against the day recorded ([dd6d91c](https://github.com/MarcelHoell/ha-ghost-mode/commit/dd6d91cbaadd317524bda9814be7e094ddd29524))

## [0.8.1](https://github.com/MarcelHoell/ha-ghost-mode/compare/v0.8.0...v0.8.1) (2026-07-25)


### Bug Fixes

* backfill entities that had no profile yet ([0a162fb](https://github.com/MarcelHoell/ha-ghost-mode/commit/0a162fb3ff5554fd3efbbd2a67383e396d52f2f3))

## [0.8.0](https://github.com/MarcelHoell/ha-ghost-mode/compare/v0.7.0...v0.8.0) (2026-07-25)


### Features

* let exclusions be pasted instead of clicked one at a time ([77cfb41](https://github.com/MarcelHoell/ha-ghost-mode/commit/77cfb4183c0bcfd3fa82cbc9c98371c756625996))

## [0.7.0](https://github.com/MarcelHoell/ha-ghost-mode/compare/v0.6.0...v0.7.0) (2026-07-25)


### Features

* add a forget service and clean up storage on removal ([19a946e](https://github.com/MarcelHoell/ha-ghost-mode/commit/19a946e2f39deef1db73e5ba852c54f2d19afac6))


### Bug Fixes

* trust recorder's retention and stop counting outages as darkness ([555423c](https://github.com/MarcelHoell/ha-ghost-mode/commit/555423c40fb116f3be8cad2cb730707609ef5e37))

## [0.6.0](https://github.com/MarcelHoell/ha-ghost-mode/compare/v0.5.1...v0.6.0) (2026-07-25)


### Features

* measure how long things were on, not what they were at the boundary ([a907e82](https://github.com/MarcelHoell/ha-ghost-mode/commit/a907e82c233d725ae846d0e9bcd1fecf00ded937))

## [0.5.1](https://github.com/MarcelHoell/ha-ghost-mode/compare/v0.5.0...v0.5.1) (2026-07-25)


### Bug Fixes

* apply exclusions and group collapsing without waiting a day ([5c2a577](https://github.com/MarcelHoell/ha-ghost-mode/commit/5c2a57799fd07a35f52ff91e82cb8519dcde4bd6))

## [0.5.0](https://github.com/MarcelHoell/ha-ghost-mode/compare/v0.4.0...v0.5.0) (2026-07-25)


### Features

* expose the learned rhythm to a dashboard ([7d05389](https://github.com/MarcelHoell/ha-ghost-mode/commit/7d05389f9b89f5bda09563318afd023ac96e535e))

## [0.4.0](https://github.com/MarcelHoell/ha-ghost-mode/compare/v0.3.0...v0.4.0) (2026-07-25)


### Features

* add an option to exclude entities from learning ([532ba73](https://github.com/MarcelHoell/ha-ghost-mode/commit/532ba73b6322d7c058b3ecf3cb410fdb6f3f6591))

## [0.3.0](https://github.com/MarcelHoell/ha-ghost-mode/compare/v0.2.0...v0.3.0) (2026-07-25)


### Features

* add a diagnostics dump of the learned rhythm ([d7bb9f5](https://github.com/MarcelHoell/ha-ghost-mode/commit/d7bb9f5b2a5f2718c32b3045892a69848cefaa6a))


### Bug Fixes

* stop a failing learning run from taking the entry down ([5a83053](https://github.com/MarcelHoell/ha-ghost-mode/commit/5a83053512e1389e3abe9354c00634067b0579e8))

## [0.2.0](https://github.com/MarcelHoell/ha-ghost-mode/compare/v0.1.0...v0.2.0) (2026-07-25)


### Features

* learn the home's rhythm from recorder history ([673c9d2](https://github.com/MarcelHoell/ha-ghost-mode/commit/673c9d2c83db76cd5a3bf8278d751c4592ad9d3c))
