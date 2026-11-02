import base64
import os
import time
from pathlib import Path

import requests
import streamlit as st

from monitoring import record_request, score_request, summarize_requests

API_BASE = "http://localhost:8000"


def auth_headers():
    token = st.session_state.get("auth_token")
    if not token:
        return {}
    return {"Authorization": f"Bearer {token}"}


def response_data(response):
    """Return JSON when available, otherwise expose a useful error message."""
    try:
        return response.json()
    except ValueError:
        return {"detail": response.text or f"Request failed with HTTP {response.status_code}"}


st.set_page_config(page_title="Customer Self Service System", page_icon="💬", layout="wide")
st.markdown(
    """
    <style>
        :root {
            --ink: #19323c;
            --muted: #60747b;
            --teal: #087f8c;
            --teal-soft: #e6f5f4;
            --coral: #e98262;
            --line: #dce9e8;
        }

        .block-container {
            max-width: 1180px;
            padding-top: 2.5rem;
            padding-bottom: 3rem;
        }

        [data-testid="stHeader"] {
            background: transparent;
        }

        .brand-mark {
            color: var(--teal);
            font-size: 0.82rem;
            font-weight: 800;
            letter-spacing: 0.12em;
            text-transform: uppercase;
            margin-bottom: 0.35rem;
        }

        .welcome-panel {
            background: linear-gradient(120deg, #e6f5f4 0%, #f8fbf7 62%, #fff1e9 100%);
            border: 1px solid var(--line);
            border-radius: 14px;
            padding: 1.7rem 2rem;
            margin: 0.3rem 0 1.5rem;
            box-shadow: 0 8px 24px rgba(25, 50, 60, 0.06);
        }

        .welcome-panel h1 {
            color: var(--ink);
            font-size: clamp(1.8rem, 3vw, 2.8rem);
            line-height: 1.08;
            margin: 0 0 0.55rem;
        }

        .welcome-panel p {
            color: var(--muted);
            font-size: 1.03rem;
            margin: 0;
            max-width: 720px;
        }

        [data-testid="stTabs"] [role="tab"] {
            color: var(--muted);
            font-weight: 700;
        }

        [data-testid="stTabs"] [role="tab"][aria-selected="true"] {
            color: var(--teal);
        }

        [data-testid="stSidebar"] {
            border-right: 1px solid var(--line);
        }

        div.stButton > button[kind="primary"] {
            background: var(--teal);
            border-color: var(--teal);
        }
    </style>
    """,
    unsafe_allow_html=True,
)
st.markdown('<div class="brand-mark">Customer care, made simple</div>', unsafe_allow_html=True)
st.markdown(
    """
    <section class="welcome-panel">
        <h1>Customer Self Service System</h1>
        <p>Welcome. Find trusted answers, ask by voice, or share an image and get helpful guidance from your knowledge base.</p>
    </section>
    """,
    unsafe_allow_html=True,
)

if "auth_token" not in st.session_state:
    st.session_state["auth_token"] = None
if "auth_user" not in st.session_state:
    st.session_state["auth_user"] = None
if "auth_role" not in st.session_state:
    st.session_state["auth_role"] = None

with st.sidebar:
    st.header("Your account")
    if st.session_state["auth_token"]:
        st.success(f"Logged in as {st.session_state['auth_user']}")
        if st.button("Logout"):
            st.session_state["auth_token"] = None
            st.session_state["auth_user"] = None
            st.session_state["auth_role"] = None
            st.rerun()
    else:
        st.subheader("Register")
        with st.form("register_form"):
            reg_username = st.text_input("New username", key="reg_username")
            reg_password = st.text_input("New password", type="password", key="reg_password")
            register_submitted = st.form_submit_button("Create account")
            if register_submitted:
                try:
                    response = requests.post(
                        f"{API_BASE}/public/register",
                        json={"username": reg_username, "password": reg_password},
                        timeout=30,
                    )
                    if response.ok:
                        st.success("Account created. You can now log in.")
                    else:
                        st.error(response_data(response).get("detail", "Registration failed"))
                except Exception as exc:
                    st.error(f"Registration error: {exc}")

        st.subheader("Login")
        with st.form("login_form"):
            username = st.text_input("Username", value="admin")
            password = st.text_input("Password", type="password", value="admin123")
            submitted = st.form_submit_button("Login")
            if submitted:
                try:
                    response = requests.post(
                        f"{API_BASE}/public/login",
                        json={"username": username, "password": password},
                        timeout=30,
                    )
                    if response.ok:
                        data = response_data(response)
                        st.session_state["auth_token"] = data.get("access_token")
                        st.session_state["auth_user"] = data.get("username")
                        st.session_state["auth_role"] = data.get("role")
                        st.success(f"Login successful as {data.get('role')}")
                        st.rerun()
                    else:
                        st.error(response_data(response).get("detail", "Invalid username or password"))
                except Exception as exc:
                    st.error(f"Unable to connect to the API: {exc}")
        st.caption("Admin account: admin / admin123")

if not st.session_state["auth_token"]:
    st.warning("Please log in to access the knowledge base and protected APIs.")
    st.stop()

st.sidebar.header("Knowledge base")
pdf_file = None
if st.session_state.get("auth_role") == "admin":
    pdf_file = st.sidebar.file_uploader("Upload PDF", type=["pdf"])
else:
    st.sidebar.info("Only administrators can upload knowledge-base documents.")

if pdf_file is not None:
    try:
        response = requests.post(
            f"{API_BASE}/pdf-upload",
            files={"file": (pdf_file.name, pdf_file.getvalue(), "application/pdf")},
            headers=auth_headers(),
            timeout=120,
        )
        data = response_data(response)
        if response.ok:
            st.sidebar.success(f"Indexed {pdf_file.name} into the knowledge base.")
        else:
            st.sidebar.error(data.get("detail") or "Unable to index this PDF.")
    except Exception as exc:
        st.sidebar.error(f"Unable to index this PDF: {exc}")

for key, default in {
    "speech_audio": None,
    "speech_result": None,
    "response_audio": None,
    "request_history": [],
}.items():
    if key not in st.session_state:
        st.session_state[key] = default

search_tab, speech_tab, image_tab, monitoring_tab = st.tabs(["Search", "Speech", "Image", "Observability"])

with search_tab:
    st.subheader("Search the knowledge base")
    query = st.text_input("Ask a question about the knowledge base", key="search_query")
    if st.button("Search", key="search_button") and query:
        started_at = time.perf_counter()
        try:
            response = requests.post(
                f"{API_BASE}/text-query",
                json={"text": query},
                headers=auth_headers(),
                timeout=120,
            )
            if response.ok:
                data = response_data(response)
                results = data.get("results", [])
                answer = data.get("answer", "")
                st.session_state["response_audio"] = None
                if answer:
                    try:
                        speech_response = requests.post(
                            f"{API_BASE}/text-to-speech",
                            json={"text": answer},
                            headers=auth_headers(),
                            timeout=60,
                        )
                        speech_data = response_data(speech_response)
                        if speech_response.ok and speech_data.get("audio_base64"):
                            st.session_state["response_audio"] = base64.b64decode(speech_data["audio_base64"])
                    except Exception:
                        st.session_state["response_audio"] = None
                st.subheader("Relevant results")
                for idx, item in enumerate(results, start=1):
                    st.markdown(f"**{idx}.** {item.get('content', '')[:400]}")
                st.subheader("Answer")
                st.write(answer)
                if st.session_state["response_audio"]:
                    st.audio(st.session_state["response_audio"], format="audio/mp3")
                record_request(
                    st.session_state["request_history"],
                    score_request(
                        "search",
                        query,
                        answer,
                        results=results,
                        latency_seconds=time.perf_counter() - started_at,
                    ),
                )
            else:
                data = response_data(response)
                record_request(
                    st.session_state["request_history"],
                    score_request(
                        "search",
                        query,
                        "",
                        latency_seconds=time.perf_counter() - started_at,
                        success=False,
                        error=data.get("detail") or "Search failed",
                    ),
                )
                if response.status_code == 401:
                    st.error("Your login session is missing or expired. Please log in again.")
                else:
                    st.error(data.get("detail") or "Search failed")
        except Exception as exc:
            record_request(
                st.session_state["request_history"],
                score_request(
                    "search",
                    query,
                    "",
                    latency_seconds=time.perf_counter() - started_at,
                    success=False,
                    error=str(exc),
                ),
            )
            st.error(f"Unable to query the API: {exc}")


with speech_tab:
    st.subheader("Speech question")
    st.caption("Record or upload audio. The speech pipeline will transcribe it and read the answer aloud.")
    recorded_audio = st.audio_input("Record a question", key="voice_recording")
    uploaded_audio = st.file_uploader("Or upload a voice note", type=["wav", "mp3", "m4a", "ogg"], key="speech_upload")
    if st.button("Process Speech", key="process_speech") and (recorded_audio is not None or uploaded_audio is not None):
        started_at = time.perf_counter()
        try:
            files = {}
            if recorded_audio is not None:
                recorded_bytes = recorded_audio.getvalue() if hasattr(recorded_audio, "getvalue") else recorded_audio.read()
                audio_path = Path("recorded_question.wav")
                audio_path.write_bytes(recorded_bytes)
                files["audio"] = (audio_path.name, audio_path.read_bytes(), "audio/wav")
            else:
                files["audio"] = (uploaded_audio.name, uploaded_audio.getvalue(), uploaded_audio.type or "audio/wav")

            response = requests.post(
                f"{API_BASE}/vlm-speech",
                data={"question": ""},
                files=files,
                headers=auth_headers(),
                timeout=(10, int(os.getenv("VLM_REQUEST_TIMEOUT", "900"))),
            )
            data = response_data(response)
            if response.ok and data.get("reasoning") and data.get("audio_base64"):
                st.session_state["speech_result"] = {
                    "transcript": data.get("transcript", ""),
                    "reasoning": data.get("reasoning", ""),
                }
                st.session_state["speech_audio"] = base64.b64decode(data["audio_base64"])
                record_request(
                    st.session_state["request_history"],
                    score_request(
                        "speech",
                        data.get("transcript", ""),
                        data.get("reasoning", ""),
                        latency_seconds=time.perf_counter() - started_at,
                    ),
                )
                st.success("Speech processing complete.")
            else:
                record_request(
                    st.session_state["request_history"],
                    score_request(
                        "speech",
                        data.get("transcript", ""),
                        "",
                        latency_seconds=time.perf_counter() - started_at,
                        success=False,
                        error=data.get("detail") or data.get("error") or "Speech request failed",
                    ),
                )
                st.error(data.get("detail") or data.get("error") or "Unable to process the speech request.")
        except Exception as exc:
            record_request(
                st.session_state["request_history"],
                score_request(
                    "speech",
                    "",
                    "",
                    latency_seconds=time.perf_counter() - started_at,
                    success=False,
                    error=str(exc),
                ),
            )
            st.error(f"Speech pipeline failed: {exc}")
        finally:
            if Path("recorded_question.wav").exists():
                Path("recorded_question.wav").unlink()

    if st.session_state["speech_result"]:
        st.markdown("### Transcript")
        st.write(st.session_state["speech_result"]["transcript"])
        st.markdown("### Answer")
        st.write(st.session_state["speech_result"]["reasoning"])
        if st.button("Play answer aloud", key="play_speech_answer") and st.session_state["speech_audio"] is not None:
            st.audio(st.session_state["speech_audio"], format="audio/mp3")


with image_tab:
    st.subheader("Image question")
    st.caption("Upload an image and ask a question about it. Image analysis is separate from search and speech.")
    image_question = st.text_input("What should I inspect in the image?", value="Describe the uploaded image.", key="image_question")
    image_file = st.file_uploader("Upload an image", type=["png", "jpg", "jpeg"], key="image_upload")
    if st.button("Analyze Image", key="analyze_image") and image_file is not None:
        started_at = time.perf_counter()
        try:
            image_bytes = image_file.getvalue()
            response = requests.post(
                f"{API_BASE}/vlm-speech",
                data={
                    "question": image_question.strip() or "Describe the uploaded image.",
                    "return_audio": "false",
                },
                files={"image": (image_file.name, image_bytes, image_file.type or "image/png")},
                headers=auth_headers(),
                timeout=(10, int(os.getenv("VLM_REQUEST_TIMEOUT", "900"))),
            )
            data = response_data(response)
            if response.ok and data.get("reasoning"):
                st.image(image_bytes, caption="Uploaded image", use_container_width=True)
                st.markdown("### Analysis")
                st.write(data.get("reasoning", ""))
                if data.get("audio_base64"):
                    st.audio(base64.b64decode(data["audio_base64"]), format="audio/mp3")
                record_request(
                    st.session_state["request_history"],
                    score_request(
                        "image",
                        image_question,
                        data.get("reasoning", ""),
                        latency_seconds=time.perf_counter() - started_at,
                    ),
                )
            else:
                record_request(
                    st.session_state["request_history"],
                    score_request(
                        "image",
                        image_question,
                        "",
                        latency_seconds=time.perf_counter() - started_at,
                        success=False,
                        error=data.get("detail") or data.get("error") or "Image request failed",
                    ),
                )
                st.error(data.get("detail") or data.get("error") or "Unable to analyze the image.")
        except Exception as exc:
            record_request(
                st.session_state["request_history"],
                score_request(
                    "image",
                    image_question,
                    "",
                    latency_seconds=time.perf_counter() - started_at,
                    success=False,
                    error=str(exc),
                ),
            )
            st.error(f"Image analysis failed: {exc}")


with monitoring_tab:
    st.subheader("Request observability")
    st.caption("Scores are calculated locally from request quality, answer presence, evidence, latency, and failures.")
    history = st.session_state["request_history"]
    summary = summarize_requests(history)
    metric_columns = st.columns(4)
    metric_columns[0].metric("Requests", summary["count"])
    metric_columns[1].metric("Average score", f"{summary['average_score']}/100")
    metric_columns[2].metric("Success rate", f"{summary['success_rate']}%")
    metric_columns[3].metric("Average latency", f"{summary['average_latency']}s")

    if history:
        display_events = [
            {
                "Time": event["timestamp"].replace("T", " ")[:19],
                "Type": event["request_type"].title(),
                "Score": event["score"],
                "Latency (s)": event["latency_seconds"],
                "Status": "Success" if event["success"] else "Failed",
                "Results": event["result_count"],
                "Query": event["query"],
            }
            for event in reversed(history)
        ]
        st.dataframe(display_events, use_container_width=True, hide_index=True)
        if st.button("Clear request history", key="clear_request_history"):
            st.session_state["request_history"] = []
            st.rerun()
    else:
        st.info("No requests have been scored in this session yet.")


with st.expander("Advanced options"):
    st.write("This UI is connected to the shared pipeline in the project root, so the API and Streamlit app both use the same retrieval logic.")
