.PHONY: setup dev share package package-win package-all api web test build demo demo-assets

setup:
	./scripts/setup.sh

dev:
	./scripts/dev.sh

share:
	./scripts/share.sh

package:
	./scripts/package.sh

package-win:
	./scripts/package.sh --target=windows

package-all:
	./scripts/package.sh --target=all

api:
	backend/.venv/bin/uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000 --reload

web:
	cd frontend && npm run dev

test:
	backend/.venv/bin/python -m pytest backend/tests -q

build:
	cd frontend && npm run build

# Static demo site: sample media from the real pipeline, then a plain-file export.
demo-assets:
	backend/.venv/bin/python scripts/make-demo-assets.py

demo:
	$(MAKE) demo-assets
	cd frontend && NEXT_PUBLIC_DEMO_MODE=1 npm run build
	@rm -f dist/ClipTokAI-Demo-Site.zip
	@mkdir -p dist && cd frontend/out && zip -rq ../../dist/ClipTokAI-Demo-Site.zip . -x '*.DS_Store*'
	@echo "Site export: frontend/out ($(shell du -sh frontend/out | cut -f1))"
	@echo "Downloadable zip: dist/ClipTokAI-Demo-Site.zip ($(shell ls -lh dist/ClipTokAI-Demo-Site.zip | awk '{print $$5}'))"
