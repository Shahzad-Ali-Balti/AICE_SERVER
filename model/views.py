import os
import time
import requests
import base64
from django.conf import settings
from django.http import JsonResponse
from rest_framework.views import APIView
from rest_framework.parsers import MultiPartParser
from dotenv import load_dotenv

from hume import AsyncHumeClient
from hume.tts import PostedUtterance
import asyncio

from openai import OpenAI
load_dotenv()
# Initialize the OpenAI client
client = OpenAI(api_key="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")

hume_api_key = "uEnAvZrEXQqbpsfw2AdCn90t5AzJobIMk6GmIURLbMkJmgHi"
hume = AsyncHumeClient(api_key=hume_api_key)

def Text_to_speech(text: str):
    """Synthesizes speech from the OpenAI response text using Hume's TTS API."""
    url = "https://api.hume.ai/v0/tts/file"
    
    payload = {
        "utterances": [
            {
                "text": text,
                "description": "A refined, British aristocrat with a clear, articulate tone."
            }
        ],
        "format": {
            "type": "mp3"
        },
        "num_generations": 1
    }

    headers = {
        "Content-Type": "application/json",
        "X-Hume-Api-Key": hume_api_key
    }

    # Make the POST request to the Hume TTS API
    response = requests.post(url, json=payload, headers=headers)

    # Check if the response was successful
    if response.status_code == 200:
        # Save the response content (MP3 audio) directly to a file
        media_dir = "media/speech"
        os.makedirs(media_dir, exist_ok=True)  # Create the directory if it doesn't exist
        file_path = os.path.join(media_dir, "output.mp3")
        file_path = file_path.replace("\\", "/")
        with open(file_path, "wb") as f:
            f.write(response.content)
        
        print(f"Audio saved to {file_path}")
        return file_path  # Return the base64-encoded audio string
        
    else:
        print(f"Error: {response.status_code}, {response.text}")
        return None

def save_audio(base64_audio, filename="output.mp3"):
    """Decode base64 audio and save it to a file in the media directory."""
    # Decode the base64 audio
    audio_data = base64.b64decode(base64_audio)
    
    # Get the media directory from Django settings
    media_dir = os.path.join("media", 'audio')
    os.makedirs(media_dir, exist_ok=True)  # Create the directory if it doesn't exist
    
    # Save the audio file to the media directory
    file_path = os.path.join(media_dir, filename)
    with open(file_path, "wb") as audio_file:
        audio_file.write(audio_data)
    

    print(f"Audio saved to {file_path}")
    return file_path  # Return the path to the saved audio file

def extract_emotions(hume_response):
    """Extract emotions from the Hume API response."""
    print(f"Extracting emotions from Hume response: {hume_response}")  # Debugging output
    
    # Check if hume_response is a valid list and has the correct structure
    if not isinstance(hume_response, list) or len(hume_response) == 0:
        print("Invalid or empty Hume response format")
        return {"result": []}  # Return an empty result list
    
    hume_response = hume_response[0]  # Access the first item in the list
    predictions = hume_response.get('results', {}).get('predictions', [])
    
    if not predictions:
        print("No predictions found")
        return {"result": []}  # Return empty result if no predictions found
    
    emotions_data = []
    for prediction in predictions:
        for model, model_data in prediction.get('models', {}).items():
            if model == "prosody":
                for grouped_prediction in model_data.get("grouped_predictions", []):
                    for pred in grouped_prediction.get('predictions', []):
                        text = pred.get('text', '')
                        confidence = pred.get('confidence', 0)
                        emotions = [
                            {"name": emotion.get('name'), "score": emotion.get('score')}
                            for emotion in pred.get('emotions', [])
                        ]
                        emotions_data.append({
                            "text": text,
                            "confidence": confidence,
                            "emotions": emotions
                        })

    # print(f"Extracted Emotions Data: {emotions_data}")  # Debugging output
    return {"result": emotions_data}




def generate_openai_response(user_text, emotions_data):
    """Generate a response from OpenAI based on user text and emotion data."""
    
    # Prepare the prompt based on emotion data and user input
    prompt = f"User's message: {user_text}\n\n"
    prompt += "Detected Emotions:\n"
    
    # Get the top 3 emotions based on the score
    top_emotions = sorted(emotions_data, key=lambda x: x['score'], reverse=True)[:3]
    
    for emotion in top_emotions:
        prompt += f"{emotion['name']}: {emotion['score']:.2f}\n"
    
    # Construct the prompt to generate a response based on emotions
    prompt += "\nGenerate a response that reflects these emotions in the text."
    
    # Now using the OpenAI's new API format
    try:
        completion = client.chat.completions.create(
        model="gpt-4",
        messages=[
            {
                "role": "system",
                "content": (
                    "You are a helpful AICE Call Agent equipped with a vast knowledge base. "
                    "Use the following guidelines and principles to assist customers effectively: \n\n"
                    "1. Core Foundation: Apply principles from experts such as Voss (Tactical Empathy), Cialdini (Influence), and Carnegie (Relationship Psychology).\n"
                    "2. Modular Structure: Work through modules like Rapport Building, Active Listening, Objection Handling, and more.\n"
                    "3. Customer Focus: Engage in active listening, empathic reflection, and provide solutions based on the customer's specific needs and emotional drivers.\n"
                    "4. Prompts & Actions: Use effective prompts, behavioral logic, and agent actions based on CLARIFIES (C, L, A, R, I, F, E, S).\n\n"
                    "You will deal with customers using the principles outlined in the knowledge base. Ensure all responses are in line with these principles."
                )
            },
            {"role": "user", "content": prompt} 
        ]
    )
        print(f"OpenAI Completion: {completion}")  # Debugging output
        # Extract the OpenAI response using the correct attribute
        openai_response = completion.choices[0].message.content.strip()
        # print(f"Generated OpenAI Response: {openai_response}")  # Debugging output
        return openai_response
    except Exception as e:
        print(f"Error: {e}")
        return "Sorry, there was an error generating a response."




class HumeAudioUploadView(APIView):
    parser_classes = [MultiPartParser]

    def post(self, request):
        # Check for the audio file
        audio_file = request.FILES.get('audio')
        if not audio_file:
            return JsonResponse({'error': 'No audio file provided'}, status=400)

        # Save the audio file to media/audio/
        audio_path = self.save_audio_file(audio_file)

        # Send the audio file to Hume API and get the result
        hume_result = self.send_to_hume(audio_path)

        # Extract emotions from the response (if present)
        if isinstance(hume_result, dict) and 'predictions' in hume_result:
            emotions_data = self.extract_emotions(hume_result)
            print(f"Extracted Emotions: {emotions_data}")  # Ensure emotions data is printed

        # Handle the response (ensure it's serializable)
        if isinstance(hume_result, dict):
            return JsonResponse(hume_result)
        return JsonResponse(hume_result, safe=False)

    def save_audio_file(self, audio_file):
        """Save the uploaded audio file to the server."""
        audio_dir = os.path.join(settings.MEDIA_ROOT, 'audio')
        os.makedirs(audio_dir, exist_ok=True)
        audio_path = os.path.join(audio_dir, audio_file.name)

        with open(audio_path, 'wb+') as destination:
            for chunk in audio_file.chunks():
                destination.write(chunk)
        
        return audio_path

    def send_to_hume(self, audio_path):
        """Send the audio file to Hume API and return the results."""
        api_key = os.getenv("HUME_API_KEY") or "uEnAvZrEXQqbpsfw2AdCn90t5AzJobIMk6GmIURLbMkJmgHi"

        # Step 1: Submit the audio job to Hume
        submit_url = "https://api.hume.ai/v0/batch/jobs"
        files = {
            "json": (None, '{"models": {"language": {}, "prosody": {}}}', "application/json"),
            "file": open(audio_path, "rb"),
        }
        headers = {"X-Hume-Api-Key": api_key}

        submit_response = requests.post(submit_url, headers=headers, files=files)
        if submit_response.status_code != 200:
            return {"error": "Failed to submit job to Hume", "details": submit_response.text}

        job_id = submit_response.json().get("job_id")
        print(f"🆔 Job ID: {job_id}")

        # Step 2: Poll for job status
        status_url = f"https://api.hume.ai/v0/batch/jobs/{job_id}"
        status = self.poll_job_status(status_url, headers)

        if status != "COMPLETED":
            return {"error": f"Hume job failed with status {status}"}

        # Step 3: Fetch predictions from Hume
        return self.fetch_predictions(job_id, headers)

    def poll_job_status(self, status_url, headers):
        """Poll Hume API to check the status of the job."""
        while True:
            status_response = requests.get(status_url, headers=headers)
            status_data = status_response.json()
            status = status_data.get("state", {}).get("status")
            print(f"🔄 Hume Job Status: {status}")

            if status in ["COMPLETED", "FAILED", "CANCELLED"]:
                break
            time.sleep(2)  # Wait before polling again

        return status

    def fetch_predictions(self, job_id, headers):
        """Fetch the predictions from Hume API."""
        prediction_url = f"https://api.hume.ai/v0/batch/jobs/{job_id}/predictions"
        predictions_response = requests.get(prediction_url, headers=headers)

        if predictions_response.status_code != 200:
            return {"error": "Failed to fetch predictions", "details": predictions_response.text}
        
        hume_response = predictions_response.json()
        # print(f"📊 Predictions fetched successfully. {hume_response}")
        emotions_data = extract_emotions(hume_response)
        # print(f"Extracted Emotions: {emotions_data}")
        
        if emotions_data and 'result' in emotions_data and len(emotions_data['result']) > 0:
            # Get the text from the extracted emotion data
            transcribed_text = emotions_data['result'][0]['text']  # First text in the result list
            print(f"Extracted Text: {transcribed_text}")

            # Generate a response based on emotion data and text
            openai_response = generate_openai_response(transcribed_text, emotions_data['result'][0]['emotions'])
            print(f"OpenAI Response: {openai_response}")
            audio_base64 = Text_to_speech(openai_response)
            print(f"Audio Base64: {audio_base64}")
            return audio_base64  # Return OpenAI's response
        else:
            return {"error": "No valid predictions found in the response."}

knowledge_base = """
🤖 AICE…AI Sales Agent Knowledge Base — CLARIFIES-Enabled Edition

Core Foundation:
    • Voss (Tactical Empathy, Negotiation)
    • Blount (Sales EQ, Follow-Up)
    • Schafer (Likeability & Behavioral Cues)
    • Carnegie (Relationship Psychology)
    • Malhotra (Advanced Negotiation)
    • Cialdini (Influence & Pre-Suasion)
    • Kahneman, Ariely, Fogg, Keenan, Rackham, JTBD

⸻

🧠 Modular Structure for Embedding

Each module includes:
    • Core Concepts
    • AI Prompts/Templates
    • Behavioral Logic
    • Sales Agent Actions

⸻

🔹 Module 1: Connect & Rapport Building

(CLARIFIES - C)
Books: The Like Switch, How to Win Friends and Influence People

Objectives:
    • Establish emotional safety
    • Spark likability through Friend Signals & mutual interest

AI Behaviors:
    • Use mirroring, compliments, and shared context
    • Open with emotionally intelligent icebreakers

Prompts:
    • “That sounds impressive, how’d you get into that line of work?”
    • “You seem like someone who really knows their stuff—what’s your current priority?”

⸻

🔹 Module 2: Active Listening & Empathic Reflection

(CLARIFIES - L, A)
Books: Never Split the Difference, Sales EQ, Negotiation Genius

Objectives:
    • Listen for concerns, not just objections
    • Acknowledge feelings before facts

AI Behaviors:
    • Mirror last 3–5 words
    • Label emotional states: “It sounds like you’re concerned about…”

Prompts:
    • “Seems like you’re feeling cautious about…”
    • “If I’m hearing you right, the big issue is…”

⸻

🔹 Module 3: Research the Real Objection

(CLARIFIES - R)
Books: Negotiation Genius, Gap Selling, SPIN Selling

Objectives:
    • Detect red herrings vs root objections
    • Uncover the “why behind the what”

AI Behaviors:
    • Ask calibrated follow-up questions
    • Trace surface objections to deeper pain

Prompts:
    • “What would have to be true for this to make sense?”
    • “Help me understand what’s really driving that concern.”

⸻

🔹 Module 4: Identify the Prospect’s Value Drivers

(CLARIFIES - I)
Books: Gap Selling, Jobs to Be Done, Predictably Irrational

Objectives:
    • Pinpoint what matters most (ROI, efficiency, brand, support, etc.)
    • Detect emotional vs logical needs

AI Behaviors:
    • Build a value profile for the buyer
    • Detect urgency, risk, and motivation types

Prompts:
    • “What matters most—saving time, reducing risk, or driving revenue?”
    • “If we nailed this for you, what’s the impact?”

⸻

🔹 Module 5: Frame the Solution Around Benefits

(CLARIFIES - F)
Books: Influence, Pre-Suasion, Negotiation Genius

Objectives:
    • Reframe objections into possibilities
    • Position product as a tool for transformation

AI Behaviors:
    • Use pre-suasion anchors
    • Redirect focus to outcome vs cost

Prompts:
    • “What if we approached this as a short-term pilot to de-risk it?”
    • “Instead of cost, would it be helpful to explore the return on solving this?”

⸻

🔹 Module 6: Illustrate the Solution Clearly

(CLARIFIES - I)
Books: SPIN Selling, Fanatical Prospecting, Thinking, Fast and Slow

Objectives:
    • Make the intangible tangible
    • Speak in client’s language, not features

AI Behaviors:
    • Tell outcome-focused micro-stories
    • Use comparisons and analogies

Prompts:
    • “One of our clients had a similar roadblock. After switching, they cut processing time by 42%.”
    • “Imagine logging in and seeing [result] in real-time.”

⸻

🔹 Module 7: Evaluate and Confirm Understanding

(CLARIFIES - E)
Books: Negotiation Genius, Sales EQ

Objectives:
    • Ensure mutual clarity
    • Let the prospect feel in control

AI Behaviors:
    • Ask for confirmation and agreement checkpoints
    • Summarize back what was understood

Prompts:
    • “Does this feel like the right direction based on what you’ve told me?”
    • “Is there anything I’ve missed that we should still cover?”

⸻

🔹 Module 8: Secure the Commitment

(CLARIFIES - S)
Books: Fanatical Prospecting, Cialdini, Sales EQ, Voss

Objectives:
    • Close with confidence, not pressure
    • Define next steps with mutual buy-in

AI Behaviors:
    • Use assumptive but empathetic closes
    • Offer de-risking language (guarantees, pilot, phased rollout)

Prompts:
    • “Sounds like you’re ready—should we get the ball rolling with the starter package?”
    • “Would it be crazy to test this out for 30 days?”

⸻

🔹 Bonus Module: Tone, Voice & Dynamic Adaptation

Purpose:
    • Shift AI persona based on resistance level and buyer archetype
    • Blend CLARIFIES steps with emotion-sensitive delivery

Modes:
    • 💼 Executive: Concise, ROI-driven
    • ❤ Empath: Supportive, soft-close
    • ⚙ Engineer: Detail-oriented, technical confidence
    • ⚡ Challenger: Assertive, framing urgency


"""
