ffmpeg \
	-framerate 29.97 \
	-pattern_type glob \
	-i 'image_sequence/bad_apple_*.png' \
	-i bad_apple.wav \
	-c:a aac \
	-shortest \
	-c:v libx264 \
	-pix_fmt yuv420p \
	output.mp4