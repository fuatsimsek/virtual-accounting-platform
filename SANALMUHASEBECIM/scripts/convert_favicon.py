import cairosvg
import os

# Get the current directory
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)

# Input and output paths
svg_path = os.path.join(project_root, 'static', 'images', 'favicon.svg')
png_path = os.path.join(project_root, 'static', 'images', 'favicon.png')

# Convert SVG to PNG
cairosvg.svg2png(url=svg_path, write_to=png_path, output_width=32, output_height=32)

print(f"Favicon converted successfully: {png_path}") 