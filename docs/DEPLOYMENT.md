# Docker and public deployment

## Current status

The real-data dashboard and API were verified live on the user's computer. Source is now public at https://github.com/rishabhghosh54-spec/retainiq. GitHub Actions run 42642664418 passed all 34 Python tests and synthetic training on Linux/Python 3.12. Its Docker image built and generated the synthetic experiment successfully. The initial health probe failed on an immediate connection reset before startup; the retry policy now covers transient resets and [run 42643413362](https://github.com/rishabhghosh54-spec/retainiq/actions/runs/42643413362) passed Python tests, synthetic training, Docker build, synthetic generation inside the image, container startup and HTTP health verification. Local Docker Desktop remains unverified and is no longer required for this publishing route. Streamlit hosting is pending user account sign-in and acceptance of its terms; no hosted deployment is claimed.

The public entrypoint `streamlit_app.py` and `Dockerfile.demo` are now prepared. The entrypoint creates a small deterministic synthetic experiment on first startup, reuses it on reruns, visibly identifies synthetic mode, and overrides any real-data artifact environment path. It refuses a non-synthetic report or subscriber IDs in its own cache folder. Tests verified this boundary. No Kaggle credentials, restricted files, real trained binary, or subscriber-level outputs are needed to use this public demo.

Verification after this preparation: **32 tests passed, two in-process HTTP tests deselected, in 28.80 seconds**. The public entrypoint rendered successfully under Streamlit's application test, and the privacy-boundary checks passed. The deselected tests remain subject to the known Windows socket setup limitation; seven separate live browser HTTP checks had already passed. A fresh Linux dependency installation and all 34 tests have since passed in GitHub Actions; Docker container health has also passed; cloud deployment remains pending. No raw data, artifacts, `.env` or Kaggle credential files are tracked in Git; Streamlit secrets are excluded from both Git and the Docker build context.

## Recommended first hosting route

Use [Streamlit Community Cloud](https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/deploy) for the public synthetic dashboard. Its GitHub/entrypoint workflow does not require a local Docker installation. The root `requirements.txt` declares the public dashboard dependencies as described in [Streamlit's dependency guide](https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/app-dependencies).

After publishing the reviewed source to the intended GitHub repository:

- Repository: `rishabhghosh54-spec/retainiq`.
- Branch: `main`.
- App file: `streamlit_app.py`.
- Python: select 3.14 to match the locally checked public-entrypoint environment if offered. The Docker configuration separately targets 3.12; that Linux environment passed all 34 tests and synthetic training in CI. The pinned packages declare compatible Python requirements, but that is not a substitute for a successful hosted build.
- Secrets: none required for the synthetic demo.

The hosting service requires GitHub authentication and repository access. The user handles account authorization and any permission/terms decisions. Source publication was authorized and completed; hosting still requires account sign-in.

Public visitors see synthetic examples and synthetic metrics. Measured KKBOX research results remain in the aggregate README/model-card evidence, clearly scoped to the sampled experiment. Do not replace the public entrypoint with the private real-data dashboard or upload `data/`, `artifacts/`, credentials, or customer-level exports.

To preview the exact public entrypoint locally after dependency installation:

```powershell
streamlit run streamlit_app.py --server.port=8502
```

Port 8502 avoids the already running real-data dashboard on port 8501. Public inference API hosting is not included in this Community Cloud dashboard configuration. The locally verified API remains a separate service; hosting it requires a separate service plan, authentication and deployment verification.

## Docker path

If local Docker verification is desired, install and start Docker Desktop using the [official Windows instructions](https://docs.docker.com/desktop/setup/install/windows-install/). Its prerequisites/backend setup depend on the machine, so installation, virtualization/WSL changes and any required restarts are user-managed. No installer or system configuration was changed by the assistant.

From the project root after Docker is available:

```powershell
docker version
docker build -f Dockerfile.demo -t retainiq-public-demo .
docker run --rm -p 127.0.0.1:8502:8501 retainiq-public-demo
```

Open http://localhost:8502. This image runs as a non-root user, copies only source/configuration/dependency files, generates synthetic records in its own writable folder, and has a Streamlit health check. Its dependency installation, synthetic generation, container startup and health endpoint were verified in GitHub Actions on Linux. This does not verify the private compose stack or a public hosted URL.

The existing `Dockerfile` and `compose.yaml` serve the full local API/dashboard with read-only artifact mounts. Their default artifact configuration is the locally trained demo; select reference artifact paths explicitly for private use. Do not publish the private compose stack on a public interface.

## CI verification prepared

The GitHub workflow now includes a Docker job which builds `Dockerfile.demo`, generates the synthetic experiment inside the image, starts the Streamlit container, checks its health endpoint, collects logs and removes the named test container. The ordinary test job also checks the public-entrypoint privacy boundary. These jobs have been executed remotely; see the current status above. An actual green run and a browser check of the hosted URL are required before claiming deployment success.

The image structure/health endpoint follows [Streamlit's Docker guidance](https://docs.streamlit.io/deploy/tutorials/docker). A Dockerfile is packaging configuration, not proof that an image was built or a site deployed.
