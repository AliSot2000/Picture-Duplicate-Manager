# Purpose of this Branch

This is the old version of the gui interface for the photo database. It is the current progress of the project before devellopement was halted. 
Currently, kivy has been replaced by QT because of missing features in kivy, namely a missing horizontal scrolling with modifier keys.

The new version of the GUI is more feature rich than the kivy gui. 
Additionally, the kivy gui still uses Difpy v2.4.5 the new version will be using fast_diff_py with the (currently not implemented) non-embedded process.
That should be significantly faster and scale better with more cpu power.

