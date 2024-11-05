from django.shortcuts import render
from django.http import HttpResponse, FileResponse
from google.cloud import texttospeech
import os
import uuid
from moviepy.editor import *
from django.core.files.storage import default_storage
from django.utils.text import slugify
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings


client = texttospeech.TextToSpeechClient()


@csrf_exempt
def home(request):
    if request.method == 'POST':
        script = request.POST.get('script', '')
        media_file = request.FILES.get('media')
        use_chapters = 'use_chapters' in request.POST

        audio_filenames = None
        audio_filename = None
        video_filename = None

        filename = f"{slugify(os.path.splitext(media_file.name)[0])}_{uuid.uuid4()}{os.path.splitext(media_file.name)[1]}"
        media_path = default_storage.save(f'uploads/{filename}', media_file)
        media_path_full = os.path.join(settings.MEDIA_ROOT, media_path)

        if not os.path.exists(media_path_full):
            raise FileNotFoundError(
                f"Midia file didnt find: {media_path_full}")

        try:
            if use_chapters:
                audio_filenames = generate_audio_for_chapters(script)
                video_filename = create_video_for_chapters(
                    media_path_full, audio_filenames, script)
            else:
                audio_filename = generate_audio(script)
                video_filename = create_video(media_path_full, audio_filename)

            response = FileResponse(
                open(video_filename, 'rb'), as_attachment=True)
            response[
                'Content-Disposition'] = f'attachment; filename="{os.path.basename(video_filename)}"'
            return response

        finally:
            if media_path_full and os.path.exists(media_path_full):
                os.remove(media_path_full)

            if use_chapters:
                for audio_file in audio_filenames:
                    if audio_file and os.path.exists(audio_file):
                        os.remove(audio_file)
            else:
                if audio_filename and os.path.exists(audio_filename):
                    os.remove(audio_filename)

            if video_filename and os.path.exists(video_filename):
                os.remove(video_filename)

    return render(request, 'generator/home.html')


def generate_audio(text):
    synthesis_input = texttospeech.SynthesisInput(text=text)
    voice = texttospeech.VoiceSelectionParams(
        language_code="pt-BR", ssml_gender=texttospeech.SsmlVoiceGender.SSML_VOICE_GENDER_UNSPECIFIED)
    audio_config = texttospeech.AudioConfig(
        audio_encoding=texttospeech.AudioEncoding.MP3)

    response = client.synthesize_speech(
        input=synthesis_input, voice=voice, audio_config=audio_config)

    audio_filename = f"media/audio_{uuid.uuid4()}.mp3"
    with open(audio_filename, "wb") as out:
        out.write(response.audio_content)

        if not os.path.exists(audio_filename):
            raise FileNotFoundError(
                f"Error creating audio file: {audio_filename}")

    return audio_filename


def create_video(media_path_full, audio_filename):
    os.makedirs("media", exist_ok=True)
    output_video = f"media/video_{uuid.uuid4()}.mp4"

    if media_path_full.lower().endswith(('png', 'jpg', 'jpeg')):
        image_clip = ImageClip(media_path_full).set_duration(
            AudioFileClip(audio_filename).duration)
    else:
        image_clip = VideoFileClip(media_path_full)

    audio_clip = AudioFileClip(audio_filename)
    final_clip = image_clip.set_audio(audio_clip)

    try:
        final_clip.write_videofile(
            output_video, codec='libx264', audio_codec='aac', fps=24)
    except Exception as e:
        print(f"Error creating video: {e}")
        return None

    return output_video


def generate_audio_for_chapters(script):
    chapters = script.split('---')
    audio_filenames = []
    for chapter in chapters:
        audio_filename = generate_audio(chapter)
        audio_filenames.append(audio_filename)
    return audio_filenames


def create_video_for_chapters(media_path, audio_filenames, subtitles=None):
    clips = []
    chapters = subtitles.split(
        '---') if subtitles else [""] * len(audio_filenames)

    for audio_filename, chapter_text in zip(audio_filenames, chapters):
        if media_path.lower().endswith(('png', 'jpg', 'jpeg')):
            image_clip = ImageClip(media_path).set_duration(
                AudioFileClip(audio_filename).duration)
        else:
            image_clip = VideoFileClip(media_path)

        audio_clip = AudioFileClip(audio_filename)
        final_clip = image_clip.set_audio(audio_clip)

        final_clip = add_subtitles_to_video(final_clip, chapter_text)

        clips.append(final_clip)

    final_video = concatenate_videoclips(clips)

    os.makedirs("media", exist_ok=True)
    output_video = f"media/long_video_{uuid.uuid4()}.mp4"

    try:
        final_video.write_videofile(
            output_video, codec='libx264', audio_codec='aac', fps=24)
    except Exception as e:
        print(f"Error creating video: {e}")
        return None

    return output_video


def add_subtitles_to_video(video_clip, text):
    subtitle = TextClip(text, fontsize=24, color="white")
    subtitle = subtitle.set_position(
        'bottom').set_duration(video_clip.duration)
    final_clip = CompositeVideoClip([video_clip, subtitle])
    return final_clip
