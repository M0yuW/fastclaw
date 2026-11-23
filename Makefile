.PHONY: build build-web clean release-local install test test-integration test-race coverage dev

VERSION ?= $(shell git describe --tags --always --dirty 2>/dev/null || echo "dev")
COMMIT  ?= $(shell git rev-parse --short HEAD 2>/dev/null || echo "unknown")
DATE    ?= $(shell date -u +"%Y-%m-%dT%H:%M:%SZ")
LDFLAGS  = -s -w -X main.version=$(VERSION) -X main.commit=$(COMMIT) -X main.date=$(DATE)

build-web:
	cd web && pnpm install --frozen-lockfile && pnpm build
	rm -rf internal/setup/web
	cp -r web/out internal/setup/web

build: build-web
	CGO_ENABLED=0 go build -ldflags "$(LDFLAGS)" -o bin/fastclaw ./cmd/fastclaw

install: build
	cp bin/fastclaw /usr/local/bin/fastclaw

test:
	go test ./...

test-integration:
	go test -count=1 ./cmd/fastclaw ./internal/api ./internal/auth ./internal/eval ./internal/evaltenant ./internal/gateway ./internal/setup ./internal/store -run Integration

test-race:
	go test -race ./cmd/fastclaw ./internal/agent ./internal/api ./internal/auth ./internal/bus ./internal/eval ./internal/evaltenant ./internal/gateway ./internal/setup ./internal/store ./internal/taskqueue

coverage:
	go test ./... -coverprofile=coverage.out
	go tool cover -func=coverage.out | tail -n 1

dev: build-web
	air

clean:
	rm -rf bin/ dist/ tmp/

# Build all platforms
release-local: build-web
	@mkdir -p dist
	@# macOS
	GOOS=darwin  GOARCH=arm64 CGO_ENABLED=0 go build -ldflags "$(LDFLAGS)" -o dist/fastclaw_darwin_arm64/fastclaw  ./cmd/fastclaw
	GOOS=darwin  GOARCH=amd64 CGO_ENABLED=0 go build -ldflags "$(LDFLAGS)" -o dist/fastclaw_darwin_amd64/fastclaw  ./cmd/fastclaw
	@# Linux
	GOOS=linux   GOARCH=arm64 CGO_ENABLED=0 go build -ldflags "$(LDFLAGS)" -o dist/fastclaw_linux_arm64/fastclaw   ./cmd/fastclaw
	GOOS=linux   GOARCH=amd64 CGO_ENABLED=0 go build -ldflags "$(LDFLAGS)" -o dist/fastclaw_linux_amd64/fastclaw   ./cmd/fastclaw
	@# Windows
	GOOS=windows GOARCH=amd64 CGO_ENABLED=0 go build -ldflags "$(LDFLAGS)" -o dist/fastclaw_windows_amd64/fastclaw.exe ./cmd/fastclaw
	GOOS=windows GOARCH=arm64 CGO_ENABLED=0 go build -ldflags "$(LDFLAGS)" -o dist/fastclaw_windows_arm64/fastclaw.exe ./cmd/fastclaw
	@# Package: tar.gz for unix, zip for windows
	@cd dist && for d in fastclaw_darwin_* fastclaw_linux_*; do tar -czf "$${d}.tar.gz" -C "$$d" fastclaw; done
	@cd dist && for d in fastclaw_windows_*; do (cd "$$d" && zip -q "../$${d}.zip" fastclaw.exe); done
	@echo "Release artifacts:"
	@ls -lh dist/*.tar.gz dist/*.zip 2>/dev/null
