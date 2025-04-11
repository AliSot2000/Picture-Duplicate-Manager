from photo_lib.gui.temp_new_wigets.clickable_image import ClickableImage


class ClickableTile(ClickableImage):
    """
    Property of tile is, it's always square. I.e. override the heightForWidth method to return the width.
    """
    def heightForWidth(self, a0):
        """
        Override this function to make the image tile square.
        """
        return self.width()
