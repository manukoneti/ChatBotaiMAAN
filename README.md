MAAN is a Python/Flask web application backed by local Ollama models. It provides account-based chat, weather and web lookups, translation, and image questions through a browser.

Status: experimental. This repository contains version 6. Model accuracy, response times, and installation on a clean machine still need release testing. Public visibility does not establish an open-source license; a project-wide license has not yet been selected. Bundled libraries retain their own license notices.

Start locally

Install Python with virtual-environment support and Ollama first. Windows batch launchers are included; Python commands below can also be used from a terminal. A supported Python version matrix has not yet been verified.

cd MAAN_HTTPS_v6/MAAN_HTTPS_v6
python -m venv .venv

Activate with .venv\Scripts\activate on Windows or source .venv/bin/activate on Linux/macOS, then run:

python -m pip install -r requirements.txt
ollama pull qwen3:1.7b
python app.py

Keep Ollama running. Follow the terminal prompts to create the first account, then visit http://localhost:8080. Start with local access; the default Python entry point binds to localhost.

For translation and image modes, also download the larger model:

ollama pull gemma3:4b

Windows users can use START_LOCAL.bat. START_MAAN.bat without arguments starts the public launcher, so use the explicit local launcher while testing.

Features and limitations

Account login and per-user saved chats in SQLite.

Streaming local chat using qwen3:1.7b.

Weather and web search use external services and need internet access.

Translation, image questions, image text extraction, and image translation use gemma3:4b.

Camera search sends a generated text description to web search; it is not reverse-image matching.

One inference request is processed at a time. CPU-only image processing can take minutes.

Output languages are selectable; accuracy is not guaranteed across languages.

This version does not generate images, send messages to other apps, or execute general automation commands.

Accounts and storage

Run python app.py --add-user to add an account, or python app.py --manage-user to reset passwords or enable/disable accounts. Password entry is hidden.

The application creates data/ at runtime with the session signing key, account password hashes, and chat history. MAAN_DATA can point to another private directory. Never upload this directory, screenshots of private chats, or credentials. Photos are processed in memory, but extracted text and answers are stored in chat history.

Earlier repository content included runtime data and a session key. See SECURITY.md before using an existing installation. Removing these files from the current tree does not remove them from Git history.

Public access

The optional START_ONLINE.bat launcher uses Tailscale Funnel and requires a configured Tailscale installation. Test locally first, resolve the exposed-data issue, and confirm authentication before enabling public access. Keep the host computer awake. See the application folder's README.txt for detailed feature instructions.

Contributing and release status

See CONTRIBUTING.md and RELEASE_REVIEW.md. Run python scripts/check_repo_hygiene.py before a commit. This check detects prohibited tracked paths; it is not a complete secret scanner or security audit.
