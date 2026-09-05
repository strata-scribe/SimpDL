import os

from mutagen.id3 import APIC, ID3, TALB, TIT2, TPE1, ID3NoHeaderError
from mutagen.mp4 import MP4, MP4Cover


def set_audio_metadata(file_path, title=None, artist=None, album=None, artwork_path=None):
    """
    Sets the title, artist, album, and artwork metadata for an MP3 or M4A file.

    Args:
        file_path (str): The path to the audio file.
        title (str, optional): The title of the track.
        artist (str, optional): The artist of the track.
        album (str, optional): The album of the track.
        artwork_path (str, optional): The path to the artwork image file.
    """
    if not os.path.exists(file_path):
        return

    ext = os.path.splitext(file_path)[1].lower()

    if ext == '.mp3':
        try:
            tags = ID3(file_path)
        except ID3NoHeaderError:
            tags = ID3()

        if title:
            tags.delall('TIT2')
            tags.add(TIT2(encoding=3, text=title))
        if artist:
            tags.delall('TPE1')
            tags.add(TPE1(encoding=3, text=artist))
        if album:
            tags.delall('TALB')
            tags.add(TALB(encoding=3, text=album))
        if artwork_path and os.path.exists(artwork_path):
            with open(artwork_path, 'rb') as img_in:
                img_data = img_in.read()
            mime_type = 'image/jpeg' if artwork_path.lower().endswith(('.jpg', '.jpeg')) else 'image/png'
            tags.delall('APIC')
            tags.add(APIC(
                encoding=3,
                mime=mime_type,
                type=3,  # 3 is for front cover
                desc='Cover',
                data=img_data
            ))
        tags.save(file_path, v2_version=3)

    elif ext == '.m4a':
        audio = MP4(file_path)

        if title:
            audio['\xa9nam'] = [title]
        if artist:
            audio['\xa9ART'] = [artist]
        if album:
            audio['\xa9alb'] = [album]
        if artwork_path and os.path.exists(artwork_path):
            with open(artwork_path, 'rb') as img_in:
                img_data = img_in.read()
            image_format = MP4Cover.FORMAT_JPEG if artwork_path.lower().endswith(('.jpg', '.jpeg')) else MP4Cover.FORMAT_PNG
            audio['covr'] = [MP4Cover(img_data, imageformat=image_format)]

        audio.save()
