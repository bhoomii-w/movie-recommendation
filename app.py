import os
import tempfile

import streamlit as st
from google import genai
from streamlit_mic_recorder import mic_recorder
from gtts import gTTS
from pydub import AudioSegment
import speech_recognition as sr


# ============================================================
# CONFIGURATION
# ============================================================

st.set_page_config(
    page_title="Voice Movie Recommendation Assistant",
    page_icon="🎬",
    layout="centered"
)

MODEL_NAME = "gemini-2.5-flash"


# ============================================================
# GEMINI CLIENT
# ============================================================

@st.cache_resource
def get_client():
    """
    Creates and caches the Gemini API client.
    The API key is stored securely in Streamlit secrets.
    """
    api_key = st.secrets.get("GEMINI_API_KEY")

    if not api_key:
        st.error(
            "Gemini API key is missing. "
            "Add GEMINI_API_KEY to your Streamlit secrets."
        )
        st.stop()

    return genai.Client(api_key=api_key)


client = get_client()


# ============================================================
# SESSION STATE
# ============================================================

if "stage" not in st.session_state:
    st.session_state.stage = "industry"

if "last_transcript" not in st.session_state:
    st.session_state.last_transcript = ""

if "last_match" not in st.session_state:
    st.session_state.last_match = ""

if "recommendations" not in st.session_state:
    st.session_state.recommendations = None

if "audio_file" not in st.session_state:
    st.session_state.audio_file = None

if "preferences" not in st.session_state:
    st.session_state.preferences = {
        "industry": None,
        "genre": None,
        "mood": None,
        "era": None
    }


# ============================================================
# AUDIO TRANSCRIPTION
# ============================================================

def transcribe_audio(audio_bytes):
    """
    Converts microphone audio from WEBM to WAV
    and transcribes it using Google Speech Recognition.
    """

    webm_path = None
    wav_path = None

    try:
        # Create temporary WEBM file
        with tempfile.NamedTemporaryFile(
            delete=False,
            suffix=".webm"
        ) as webm_file:

            webm_file.write(audio_bytes)
            webm_path = webm_file.name

        # Create WAV path
        wav_path = webm_path.replace(
            ".webm",
            ".wav"
        )

        # Convert WEBM → WAV
        audio = AudioSegment.from_file(
            webm_path,
            format="webm"
        )

        audio.export(
            wav_path,
            format="wav"
        )

        # Speech recognition
        recognizer = sr.Recognizer()

        with sr.AudioFile(wav_path) as source:
            audio_data = recognizer.record(source)

        transcript = recognizer.recognize_google(
            audio_data
        )

        return transcript.strip()

    except sr.UnknownValueError:
        st.error(
            "I could not understand the audio. "
            "Please speak clearly and try again."
        )
        return None

    except sr.RequestError:
        st.error(
            "Speech recognition service is unavailable. "
            "Please check your internet connection."
        )
        return None

    except Exception as error:
        st.error(
            f"Speech recognition error: {error}"
        )
        return None

    finally:
        # Always remove temporary files
        for file_path in [webm_path, wav_path]:
            if file_path and os.path.exists(file_path):
                try:
                    os.remove(file_path)
                except OSError:
                    pass


# ============================================================
# VOICE OPTION MATCHING
# ============================================================

def match_voice_option(transcript, options):
    """
    Matches spoken text against the available options.
    """

    if not transcript:
        return None

    transcript = transcript.lower().strip()

    for option in options:
        if option.lower() in transcript:
            return option

    return None


# ============================================================
# MOVIE RECOMMENDATIONS
# ============================================================

def fetch_recommendations():
    """
    Sends the user's preferences to Gemini
    and returns movie recommendations.
    """

    preferences = st.session_state.preferences

    prompt = f"""
You are a movie recommendation assistant.

Recommend exactly 5 real movies based on these preferences:

Industry: {preferences["industry"]}
Genre: {preferences["genre"]}
Mood: {preferences["mood"]}
Era: {preferences["era"]}

Important requirements:

1. Recommend only real movies.
2. Do not invent movie titles.
3. Make sure each movie matches the user's preferences as closely as possible.
4. Give variety instead of recommending five very similar movies.
5. Keep the response concise and easy to read aloud.

For each movie, provide:

### Movie Title
- **Year:**
- **Genre:**
- **Rating:** Give an approximate IMDb-style rating, clearly presented as an approximate rating.
- **Plot:** 2–3 sentences.
- **Why You'll Like It:** 1–2 sentences.

Do not include unnecessary introduction or conclusion.
"""

    try:
        response = client.models.generate_content(
            model=MODEL_NAME,
            contents=prompt
        )

        if not response or not response.text:
            return "Sorry, I could not generate movie recommendations."

        return response.text

    except Exception as error:
        st.error(
            f"Unable to get recommendations from Gemini: {error}"
        )

        return None


# ============================================================
# TEXT TO SPEECH
# ============================================================

def speak_text(text):
    """
    Converts recommendation text into speech.
    """

    if not text:
        return None

    try:
        audio_file = tempfile.NamedTemporaryFile(
            delete=False,
            suffix=".mp3"
        )

        tts = gTTS(
            text=text,
            lang="en"
        )

        tts.save(audio_file.name)

        return audio_file.name

    except Exception as error:
        st.error(
            f"Text-to-speech error: {error}"
        )

        return None


# ============================================================
# HELPER FUNCTIONS
# ============================================================

def reset_preferences():
    """
    Resets the entire recommendation session.
    """

    st.session_state.stage = "industry"
    st.session_state.last_transcript = ""
    st.session_state.last_match = ""
    st.session_state.recommendations = None
    st.session_state.audio_file = None

    st.session_state.preferences = {
        "industry": None,
        "genre": None,
        "mood": None,
        "era": None
    }


def move_to_next_stage(stage, preference_key, value):
    """
    Saves a preference and moves the app to the next stage.
    """

    st.session_state.preferences[preference_key] = value
    st.session_state.stage = stage

    st.rerun()


# ============================================================
# HEADER
# ============================================================

st.title("🎬 Voice Movie Recommendation Assistant")

st.markdown(
    """
Choose your movie preferences using **voice or buttons**.
At the end, Gemini will generate personalized movie recommendations.
"""
)

st.markdown("---")


# ============================================================
# VOICE STATUS
# ============================================================

if st.session_state.last_transcript:
    st.info(
        f"🎤 **Last Heard:** "
        f"{st.session_state.last_transcript}"
    )

if st.session_state.last_match:
    st.success(
        f"✅ **Matched Option:** "
        f"{st.session_state.last_match}"
    )


# ============================================================
# INDUSTRY
# ============================================================

if st.session_state.stage == "industry":

    st.subheader("1️⃣ Choose Industry")

    options = [
        "Hollywood",
        "Bollywood"
    ]

    col1, col2 = st.columns(2)

    if col1.button(
        "🎞️ Hollywood",
        use_container_width=True
    ):
        move_to_next_stage(
            "genre",
            "industry",
            "Hollywood"
        )

    if col2.button(
        "🎥 Bollywood",
        use_container_width=True
    ):
        move_to_next_stage(
            "genre",
            "industry",
            "Bollywood"
        )

    st.markdown("### Or choose using your voice")

    audio = mic_recorder(
        "🎤 Speak Industry",
        "⏹ Stop",
        key="industry_mic"
    )

    if audio:
        transcript = transcribe_audio(
            audio["bytes"]
        )

        if transcript:
            st.session_state.last_transcript = transcript

            matched = match_voice_option(
                transcript,
                options
            )

            if matched:
                st.session_state.last_match = matched

                move_to_next_stage(
                    "genre",
                    "industry",
                    matched
                )

            else:
                st.session_state.last_match = ""

                st.error(
                    "I could not detect a valid industry. "
                    "Try saying Hollywood or Bollywood."
                )


# ============================================================
# GENRE
# ============================================================

elif st.session_state.stage == "genre":

    st.subheader("2️⃣ Choose Genre")

    options = [
        "Action",
        "Comedy",
        "Drama",
        "Romance",
        "Thriller",
        "Sci-Fi",
        "Horror",
        "Adventure"
    ]

    genre = st.selectbox(
        "Select Genre",
        options
    )

    col1, col2 = st.columns(2)

    if col1.button(
        "Next ➡️",
        use_container_width=True
    ):
        move_to_next_stage(
            "mood",
            "genre",
            genre
        )

    if col2.button(
        "⬅️ Back",
        use_container_width=True
    ):
        st.session_state.stage = "industry"
        st.rerun()

    st.markdown("### Or choose using your voice")

    audio = mic_recorder(
        "🎤 Speak Genre",
        "⏹ Stop",
        key="genre_mic"
    )

    if audio:
        transcript = transcribe_audio(
            audio["bytes"]
        )

        if transcript:
            st.session_state.last_transcript = transcript

            matched = match_voice_option(
                transcript,
                options
            )

            if matched:
                st.session_state.last_match = matched

                move_to_next_stage(
                    "mood",
                    "genre",
                    matched
                )

            else:
                st.session_state.last_match = ""

                st.error(
                    "I could not detect a valid genre."
                )


# ============================================================
# MOOD
# ============================================================

elif st.session_state.stage == "mood":

    st.subheader("3️⃣ Choose Mood")

    options = [
        "Happy",
        "Exciting",
        "Relaxed",
        "Romantic",
        "Scared",
        "Thoughtful",
        "Emotional",
        "Inspirational"
    ]

    mood = st.selectbox(
        "Select Mood",
        options
    )

    col1, col2, col3 = st.columns(3)

    if col1.button(
        "Next ➡️",
        use_container_width=True
    ):
        move_to_next_stage(
            "era",
            "mood",
            mood
        )

    if col2.button(
        "Skip",
        use_container_width=True
    ):
        move_to_next_stage(
            "era",
            "mood",
            "Any"
        )

    if col3.button(
        "⬅️ Back",
        use_container_width=True
    ):
        st.session_state.stage = "genre"
        st.rerun()

    st.markdown("### Or choose using your voice")

    audio = mic_recorder(
        "🎤 Speak Mood",
        "⏹ Stop",
        key="mood_mic"
    )

    if audio:
        transcript = transcribe_audio(
            audio["bytes"]
        )

        if transcript:
            st.session_state.last_transcript = transcript

            matched = match_voice_option(
                transcript,
                options
            )

            if matched:
                st.session_state.last_match = matched

                move_to_next_stage(
                    "era",
                    "mood",
                    matched
                )

            else:
                st.session_state.last_match = ""

                st.error(
                    "I could not detect a valid mood."
                )


# ============================================================
# ERA
# ============================================================

elif st.session_state.stage == "era":

    st.subheader("4️⃣ Choose Era")

    options = [
        "Classic",
        "90s",
        "2000s",
        "2010s",
        "Recent"
    ]

    era = st.selectbox(
        "Select Era",
        options
    )

    col1, col2, col3 = st.columns(3)

    if col1.button(
        "🎬 Get Recommendations",
        use_container_width=True
    ):
        move_to_next_stage(
            "result",
            "era",
            era
        )

    if col2.button(
        "Skip",
        use_container_width=True
    ):
        move_to_next_stage(
            "result",
            "era",
            "Any"
        )

    if col3.button(
        "⬅️ Back",
        use_container_width=True
    ):
        st.session_state.stage = "mood"
        st.rerun()

    st.markdown("### Or choose using your voice")

    audio = mic_recorder(
        "🎤 Speak Era",
        "⏹ Stop",
        key="era_mic"
    )

    if audio:
        transcript = transcribe_audio(
            audio["bytes"]
        )

        if transcript:
            st.session_state.last_transcript = transcript

            matched = match_voice_option(
                transcript,
                options
            )

            if matched:
                st.session_state.last_match = matched

                move_to_next_stage(
                    "result",
                    "era",
                    matched
                )

            else:
                st.session_state.last_match = ""

                st.error(
                    "I could not detect a valid era."
                )


# ============================================================
# RESULTS
# ============================================================

elif st.session_state.stage == "result":

    st.subheader("🎬 Your Movie Recommendations")

    st.markdown("### Selected Preferences")

    for key, value in st.session_state.preferences.items():
        st.write(
            f"**{key.title()}:** {value}"
        )

    st.markdown("---")

    # Generate recommendations only once
    if st.session_state.recommendations is None:

        with st.spinner(
            "🤖 Gemini is finding movies for you..."
        ):
            st.session_state.recommendations = (
                fetch_recommendations()
            )

    if st.session_state.recommendations:

        st.markdown(
            st.session_state.recommendations
        )

        # Generate audio only once
        if st.session_state.audio_file is None:

            with st.spinner(
                "🔊 Creating voice recommendations..."
            ):
                st.session_state.audio_file = (
                    speak_text(
                        st.session_state.recommendations
                    )
                )

        if st.session_state.audio_file:
            st.markdown("### 🔊 Listen to Recommendations")

            st.audio(
                st.session_state.audio_file
            )

    st.markdown("---")

    col1, col2 = st.columns(2)

    if col1.button(
        "🔄 Start Over",
        use_container_width=True
    ):
        reset_preferences()
        st.rerun()

    if col2.button(
        "⬅️ Change Preferences",
        use_container_width=True
    ):
        st.session_state.stage = "genre"
        st.session_state.recommendations = None
        st.session_state.audio_file = None
        st.rerun()


# ============================================================
# FOOTER
# ============================================================

st.markdown("---")

st.caption(
    "Built with Streamlit, Google Gemini, Speech Recognition "
    "and gTTS."
)