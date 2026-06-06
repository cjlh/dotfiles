# Video utilities - note hardcoded Mac font paths

function count-frames
    if test (count $argv) -ne 2
        echo "Usage: count-frames <input> <output>"
        return 1
    end

    set input  "$argv[1]"
    set output "$argv[2]"

    # Scale relative to video height
    set fontsize_ratio 0.06   # 6% of height
    set pad_ratio      0.00   # margin from edges
    set boxpad_ratio   0.015  # padding inside box

    set fontfile "/System/Library/Fonts/Menlo.ttc"

    ffmpeg -i "$input" \
        -vf "drawtext=fontfile='$fontfile':\
text='%{eif\\:n+1\\:d}':\
y_align=font:\
fontsize=h*$fontsize_ratio:\
x=w-tw-(h*$pad_ratio):\
y=h-th-(h*$pad_ratio):\
fontcolor=white:\
box=1:boxcolor=black@1.0:\
boxborderw=h*$boxpad_ratio" \
        -c:a copy \
        "$output"
end

# TODO remove once new script battle-tested
function count-frames-old
    if test (count $argv) -ne 2
        echo "Usage: count-frames <input> <output>"
        return 1
    end

    set input  $argv[1]
    set output $argv[2]

    # Scale relative to video height
    set fontsize_ratio 0.06   # 6% of height
    set pad_ratio      0.00   # margin from edges
    set boxpad_ratio   0.015  # padding inside box

    set fontfile "/System/Library/Fonts/Menlo.ttc"

    ffmpeg -i "$input" \
        -vf "drawtext=fontfile='$fontfile':text='%{frame_num}':\
y_align=font:\
fontsize=h*$fontsize_ratio:\
x=w-tw-(h*$pad_ratio):\
y=h-th-(h*$pad_ratio):\
fontcolor=white:\
box=1:boxcolor=black@1.0:boxborderw=h*$boxpad_ratio" \
        "$output"
end

function side-by-side-frames
    if test (count $argv) -ne 3
        echo "Usage: side-by-side-frames <left_title?:left_path> <right_title?:right_path> <output>"
        return 1
    end

    set left_spec  $argv[1]
    set right_spec $argv[2]
    set output     $argv[3]

    # Parse "title:path" (title optional)
    set left_title  ""
    set left_path   "$left_spec"
    if string match -q '*:*' -- "$left_spec"
        set left_title (string split -m 1 ':' -- "$left_spec")[1]
        set left_path  (string split -m 1 ':' -- "$left_spec")[2]
    end

    set right_title ""
    set right_path  "$right_spec"
    if string match -q '*:*' -- "$right_spec"
        set right_title (string split -m 1 ':' -- "$right_spec")[1]
        set right_path  (string split -m 1 ':' -- "$right_spec")[2]
    end

    # Config
    set gap_px 10
    set out_h  720

    # Separate size controls
    set title_size_ratio        0.03
    set frame_count_size_ratio  0.06

    set pad_ratio      0.00
    set boxpad_ratio   0.015

    set fontfile "/System/Library/Fonts/Menlo.ttc"

    # Filtergraph template
    set fg '
[0:v]scale=-2:__OUT_H__,__LEFT_TITLE__drawtext=fontfile='"'"'__FONTFILE__'"'"':text='"'"'%{frame_num}'"'"':fontsize=h*__FRAME_RATIO__:x=w-tw-(h*__PAD_RATIO__):y=h-th-(h*__PAD_RATIO__):fontcolor=white:box=1:boxcolor=black@1.0:boxborderw=h*__BOXPAD_RATIO__[L];
[1:v]scale=-2:__OUT_H__,__RIGHT_TITLE__drawtext=fontfile='"'"'__FONTFILE__'"'"':text='"'"'%{frame_num}'"'"':fontsize=h*__FRAME_RATIO__:x=w-tw-(h*__PAD_RATIO__):y=h-th-(h*__PAD_RATIO__):fontcolor=white:box=1:boxcolor=black@1.0:boxborderw=h*__BOXPAD_RATIO__[R];
color=c=black:s=__GAP_PX__x__OUT_H__:d=1[G];
[L][G][R]hstack=inputs=3:shortest=0[OUT]
'

    # Helper for escaping single quotes in titles
    function __ff_escape_single_quotes --argument-names s
        echo (string replace -a "'" "'\\''" -- "$s")
    end

    # Title filters (top-left)
    set left_title_filter ""
    if test -n "$left_title"
        set lt (__ff_escape_single_quotes "$left_title")
        set left_title_filter "drawtext=fontfile='__FONTFILE__':text='$lt':fontsize=h*__TITLE_RATIO__:x=h*__PAD_RATIO__:y=h*__PAD_RATIO__:fontcolor=white:box=1:boxcolor=black@1.0:boxborderw=h*__BOXPAD_RATIO__,"
    end

    set right_title_filter ""
    if test -n "$right_title"
        set rt (__ff_escape_single_quotes "$right_title")
        set right_title_filter "drawtext=fontfile='__FONTFILE__':text='$rt':fontsize=h*__TITLE_RATIO__:x=h*__PAD_RATIO__:y=h*__PAD_RATIO__:fontcolor=white:box=1:boxcolor=black@1.0:boxborderw=h*__BOXPAD_RATIO__,"
    end

    # Substitute placeholders
    set fg (string replace -a '__LEFT_TITLE__'  "$left_title_filter"  -- $fg)
    set fg (string replace -a '__RIGHT_TITLE__' "$right_title_filter" -- $fg)

    set fg (string replace -a '__OUT_H__' $out_h -- $fg)
    set fg (string replace -a '__GAP_PX__' $gap_px -- $fg)
    set fg (string replace -a '__TITLE_RATIO__' $title_size_ratio -- $fg)
    set fg (string replace -a '__FRAME_RATIO__' $frame_count_size_ratio -- $fg)
    set fg (string replace -a '__PAD_RATIO__' $pad_ratio -- $fg)
    set fg (string replace -a '__BOXPAD_RATIO__' $boxpad_ratio -- $fg)
    set fg (string replace -a '__FONTFILE__' $fontfile -- $fg)

    ffmpeg -i "$left_path" -i "$right_path" \
      -filter_complex "$fg" \
      -map "[OUT]" -an \
      -c:v libx264 -crf 18 -preset veryfast -pix_fmt yuv420p \
      "$output"
end

function add-audio --description "Replace a video's audio with audio from another file"
    argparse 'o/output=' -- $argv
    or begin
        echo "Usage: add-audio [--output <file>] <video_source> <audio_source>" >&2
        return 1
    end

    if test (count $argv) -ne 2
        echo "Usage: add-audio [--output <file>] <video_source> <audio_source>" >&2
        return 1
    end

    set video_source $argv[1]
    set audio_source $argv[2]

    if not test -f "$video_source"
        echo "Error: video source not found: $video_source" >&2
        return 1
    end

    if not test -f "$audio_source"
        echo "Error: audio source not found: $audio_source" >&2
        return 1
    end

    if not command -sq ffmpeg
        echo "Error: ffmpeg is not installed or not in PATH" >&2
        return 1
    end

    # Determine output path
    if set -q _flag_output
        set output_path $_flag_output
    else
        # Overwrite original: write to temp file first, then replace
        set video_dir (path dirname -- "$video_source")
        set video_name (path basename -- "$video_source")
        set temp_path (mktemp "$video_dir/add-audio.XXXXXX.$video_name")
        set output_path "$video_source"
    end

    # Run ffmpeg
    if set -q _flag_output
        ffmpeg -y \
            -i "$video_source" \
            -i "$audio_source" \
            -map 0:v:0 \
            -map 1:a:0 \
            -c:v copy \
            -c:a aac \
            -shortest \
            "$output_path"
    else
        ffmpeg -y \
            -i "$video_source" \
            -i "$audio_source" \
            -map 0:v:0 \
            -map 1:a:0 \
            -c:v copy \
            -c:a aac \
            -shortest \
            "$temp_path"

        or begin
            echo "Error: ffmpeg failed" >&2
            rm -f "$temp_path"
            return 1
        end

        mv -f "$temp_path" "$video_source"
    end

    or begin
        echo "Error: ffmpeg failed" >&2
        return 1
    end

    if set -q _flag_output
        echo "Created: $output_path"
    else
        echo "Overwritten: $video_source"
    end
end
