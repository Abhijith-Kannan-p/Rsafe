# Thin wrappers around the npm scripts, which work on Windows, macOS and Linux.
.PHONY: setup dev test seed screenshots build

setup:
	npm run setup

dev:
	npm run dev

test:
	npm run test

seed:
	npm run seed

screenshots:
	npm run screenshots

build:
	npm run build
