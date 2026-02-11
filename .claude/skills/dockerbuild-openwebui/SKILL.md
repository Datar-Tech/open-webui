---
name: dockerbuild-openwebui
description: Use when building and releasing a Docker image for open-webui/tech-sense, pushing to Docker Hub, and creating git tags. Trigger words include docker build, release, deploy, publish, version bump.
---

# Docker Build & Release for Open-WebUI

## Overview

Automates the full Docker build, push, and git tag release workflow for the tech-sense (open-webui) project. Accepts a version number and executes all steps sequentially with user confirmation.

## Usage

Invoke with: `/dockerbuild_openwebui <VERSION>`

Example: `/dockerbuild_openwebui 1.3.21`

The VERSION should be a semver string like `1.3.21` (without the `v` prefix).

## Workflow

Working directory: `C:\Github\open-webui`

Execute these steps **in order**, confirming with the user before each destructive or external action:

### Step 1: Update version in package.json

Read `package.json` and update the `"version"` field (line 3) to the new version:

```json
"version": "{VERSION}",
```

### Step 2: Docker login

Check if already logged in, then run if needed:

```bash
docker login
```

### Step 3: Build Docker image

```bash
docker build --build-arg BUILD_HASH=v{VERSION} -t tech-sense .
```

This step takes significant time. Use a long timeout (10 minutes).

### Step 4: Tag and push versioned image

```bash
docker tag tech-sense deliah/tech-sense:v{VERSION}
docker push deliah/tech-sense:v{VERSION}
```

### Step 5: Tag and push latest image

```bash
docker tag tech-sense deliah/tech-sense:latest
docker push deliah/tech-sense:latest
```

### Step 6: Create and push git tag

```bash
git tag -a v{VERSION} -m "Release v{VERSION}"
git push origin v{VERSION}
```

## Important Notes

- Always confirm with the user before running `docker push` and `git push` commands
- The `docker build` step can take several minutes - use `timeout: 600000` (10 min)
- If any step fails, stop and report the error - do not continue to subsequent steps
- The version in `package.json` should already be committed before tagging (coordinate with user)

## Common Mistakes

| Mistake | Fix |
|---------|-----|
| Forgetting `v` prefix in BUILD_HASH/tags | Always use `v{VERSION}` for docker tags and git tags |
| Running git tag before committing version bump | Ensure package.json change is committed first |
| Docker build timeout | Use 600000ms timeout for the build command |
