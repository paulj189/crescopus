# Landing page tour video

`tour.html` is the whole 1-minute video as one animated page (1920×1080). `render.js` steps it frame by frame in Chromium and pipes the frames to ffmpeg.

    cd tools/tour && node render.js            # writes out.mp4
    node render.js preview 3 15.5 28.8         # stills at those seconds

Then copy `out.mp4` to `app/static/video/crescopus-tour.mp4` (and a still to `crescopus-tour-poster.jpg`). Needs Node, Playwright and ffmpeg.
