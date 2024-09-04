import streamlit as st
import os
from PIL import Image
import pandas as pd
from sqlalchemy import create_engine, text
from google.cloud import storage
from io import BytesIO
import json
import tempfile

# Title of the page
st.title("Fine-tuning GenAI Project")

# Load Google Cloud Storage credentials
gcs_credentials = json.loads(st.secrets["database"]["credentials"])
with tempfile.NamedTemporaryFile(delete=False, mode='w', suffix='.json') as temp_file:
    json.dump(gcs_credentials, temp_file)
    temp_file_path = temp_file.name
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = temp_file_path
client = storage.Client()

# Specify your bucket name
bucket_name = 'bucketName'
bucket = client.get_bucket(bucket_name)

connection_string = st.secrets["database"]["connection_string"]
engine = create_engine(connection_string)

# Input for the image number
image_number = st.number_input("Enter Image Number:", min_value=1, value=1)

# Folder containing the images
image_folder = "Prompts/Final images moodboard/"

# Function to fetch prompts from PostgreSQL based on image number
def get_prompts(image_number):
    query = f"""
    SELECT serial_nos, sno, image_prompts, 
           COALESCE(prompt_feedback, 'GOOD') AS prompt_feedback
    FROM prompts
    WHERE sno = {image_number}
    ORDER BY serial_nos;
    """
    prompts_df = pd.read_sql(query, engine)
    return prompts_df

# Function to fetch image feedback from PostgreSQL based on image name
def get_image_feedback(image_name):
    query = text("""
    SELECT COALESCE(image_feedback, 'GOOD') AS image_feedback
    FROM images
    WHERE image = :image_name
    """)
    with engine.connect() as conn:
        result = conn.execute(query, {"image_name": image_name}).fetchone()
    return result[0] if result else 'GOOD'

# Function to update the edited prompt and feedback in the database
def update_prompt(serial_nos, new_prompt, feedback):
    try:
        serial_nos = int(serial_nos)
        update_query = text("""
        UPDATE prompts
        SET image_prompts = :new_prompt, prompt_feedback = :feedback
        WHERE serial_nos = :serial_nos
        """)
        with engine.connect() as conn:
            conn.execute(update_query, {"new_prompt": new_prompt, "feedback": feedback, "serial_nos": serial_nos})
            conn.commit()
        st.success("Prompt updated successfully!")
    except Exception as e:
        st.error(f"Failed to update prompt: {e}")

# Function to update the image review in the database
def update_image_review(image_name, review):
    try:
        update_query = text("""
        UPDATE images
        SET image_feedback = :review
        WHERE image = :image_name
        """)
        with engine.connect() as conn:
            conn.execute(update_query, {"review": review, "image_name": image_name})
            conn.commit()
        st.success("Image review updated successfully!")
    except Exception as e:
        st.error(f"Failed to update image review: {e}")

# Function to add a new prompt to the database
def add_new_prompt(image_number, new_prompt):
    try:
        insert_query = text("""
        INSERT INTO prompts (sno, image_prompts, prompt_feedback)
        VALUES (:sno, :new_prompt, 'GOOD')
        """)
        with engine.connect() as conn:
            conn.execute(insert_query, {"sno": image_number, "new_prompt": new_prompt})
            conn.commit()
        st.success("New prompt added successfully!")
    except Exception as e:
        st.error(f"Failed to add new prompt: {e}")

# Display the selected image and its prompts
image_name = f"image{image_number}.jpg"
image_path = os.path.join(image_folder, image_name)

col1, col2 = st.columns([1, 2])

with col1:
    # Load the image from Google Cloud Storage
    blob = bucket.blob(image_path)
    image_data = blob.download_as_bytes()
    image = Image.open(BytesIO(image_data))
    st.image(image, caption=f"Image {image_number}")

    # Get existing review from the database or default to "GOOD"
    image_review = get_image_feedback(image_name)
    image_review = st.radio(f"Review Image {image_number}:", ["GOOD", "BAD"], index=["GOOD", "BAD"].index(image_review), key=f"image_review_{image_number}")
    
    if st.button(f"Save Image Review {image_number}"):
        update_image_review(image_name, image_review)

with col2:
    prompts_df = get_prompts(image_number)
    if not prompts_df.empty:
        prompt_options = prompts_df['image_prompts'].tolist()
        selected_prompt_index = st.selectbox(f"Select Prompt for Image {image_number}", range(len(prompt_options)), format_func=lambda x: f"Prompt {x+1}")
        selected_prompt = prompt_options[selected_prompt_index]
        serial_nos = prompts_df.iloc[selected_prompt_index]['serial_nos']

        st.write(f"Prompt {selected_prompt_index + 1}:")
        new_prompt = st.text_area(f"Edit Prompt {selected_prompt_index + 1}", value=selected_prompt, key=f"prompt_{serial_nos}")
        prompt_review = st.radio(f"Review Prompt {selected_prompt_index + 1}", ["GOOD", "BAD"], index=["GOOD", "BAD"].index(prompts_df.iloc[selected_prompt_index]['prompt_feedback']), key=f"review_{serial_nos}")

        if st.button(f"Save Prompt {selected_prompt_index + 1}", key=f"save_prompt_{serial_nos}"):
            update_prompt(serial_nos, new_prompt, prompt_review)
    else:
        st.warning(f"No prompts found for image {image_number}.")

    st.write(f"Add a new prompt for Image {image_number}:")
    new_prompt_input = st.text_area(f"New Prompt for Image {image_number}", key=f"new_prompt_{image_number}")
    if st.button(f"Add New Prompt for Image {image_number}"):
        if new_prompt_input.strip():
            add_new_prompt(image_number, new_prompt_input)
        else:
            st.warning("New prompt cannot be empty.")