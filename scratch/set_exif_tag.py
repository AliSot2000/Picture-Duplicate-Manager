import exiftool


def set_create_date(file_path, create_date):
    """
    Set the EXIF:CreateDate tag for an image file using pyexiftool.

    Parameters:
    - file_path: Path to the image file.
    - create_date: Date in the format 'YYYY:MM:DD HH:MM:SS'.
    """
    with exiftool.ExifToolHelper() as et:
        # Prepare the EXIF tag with the correct format
        metadata = {f"EXIF:CreateDate": create_date}

        # Update the metadata
        et.set_tags(tags=metadata, files=file_path, params=["-overwrite_original"])
        print(f"Successfully set EXIF:CreateDate to {create_date} for file {file_path}.")


# Example usage:
image_path = "example.jpg"
new_create_date = "2024:12:30 12:00:00"
set_create_date(image_path, new_create_date)

# Need to set   OffsetTime = +/-
# Need to set   ModifyDate = YYYY:MM:DDTHH:MM:SS