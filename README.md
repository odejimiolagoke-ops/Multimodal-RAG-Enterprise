# Enterprise Multimodal RAG

A FastAPI and Streamlit application for querying a knowledge base using text,
PDFs, audio, and images. The application can use Supabase for persistent vector
storage and hosted AI providers for answer generation, transcription, and
vision. Without Supabase, indexed documents are held in memory and are lost
when the API process stops.

## Features

- Text question answering and knowledge-base retrieval.
- Admin-only PDF indexing.
- Audio transcription and image question answering.
- Optional text-to-speech responses.
- JWT-protected API routes and request audit logging.
- Input, upload, retrieved-context, and generated-text guardrails.

## Requirements

- Python 3.11 or newer.
- Git.
- Optional provider accounts and API keys for hosted AI features.
- A Supabase project with the `vector` extension and schema configured for
  persistent document storage.

Some packages in `requirements.txt`, including PyTorch and Whisper, are large.
Installation may take several minutes and require substantial disk space.

## Set up locally

### Windows PowerShell

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
Copy-Item .env.example .env
```

### macOS or Linux

```bash
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
cp .env.example .env
```

Edit `.env` and provide the credentials for the services you intend to use.
Never commit `.env` or paste real credentials into issues or pull requests.
`JWT_SECRET_KEY` must be set to a unique, strong random value before running
the application anywhere beyond local development.

For persistent storage, configure `SUPABASE_URL` and `SUPABASE_KEY`, then run
the SQL in [schema.py](schema.py) in the Supabase SQL editor. Use a server-side
service key; do not expose it to browsers or commit it to the repository.
Without Supabase, the application uses an in-memory document store.

At least one supported provider key is needed for hosted answer generation:
`OPENAI_API_KEY` or `OPENROUTER_API_KEY`. Speech transcription can use
`OPENAI_API_KEY` or `GROQ_API_KEY`; without one, the app attempts local Whisper
transcription. Image analysis supports the configured OpenAI, NVIDIA, or
OpenRouter providers, or an explicitly configured local `VLM_MODEL`.

## Run the application

Start the API and the web interface in separate terminals from the project
directory, with the virtual environment activated in each:

```powershell
python -m uvicorn main:app --host 127.0.0.1 --port 8000
```

```powershell
streamlit run streamlit_app.py --server.address 127.0.0.1 --server.port 8501
```

Open the Streamlit interface at <http://127.0.0.1:8501>. The API health check
is at <http://127.0.0.1:8000/health>, and interactive API documentation is at
<http://127.0.0.1:8000/docs>.

## Authentication and deployment warning

This repository is a development project, not a production-ready deployment.
The current [auth.py](auth.py) contains a built-in `admin` account with the
password `admin123` and a fallback JWT signing key. Remove or replace those
defaults before publishing a live service; set a strong `JWT_SECRET_KEY` and
use a secure user store and password hashing before accepting real accounts.
The local `users.json` file stores registered passwords in plaintext and is
excluded from Git. Public registration is enabled by the current API.

Do not expose the development server to the public internet without a security
review, secure authentication and password storage, HTTPS, appropriate
rate-limiting, and deployment-specific access controls. Keep audit logs private
and apply retention policies appropriate to the data they contain.

## Tests

Run the focused guardrail tests with:

```bash
python -m unittest test_guardrails -v
```

## Project policies

- [Governance](GOVERNANCE.md)
- [Contributing](CONTRIBUTING.md)
- [Code of conduct](CODE_OF_CONDUCT.md)
- [Security reporting](SECURITY.md)
