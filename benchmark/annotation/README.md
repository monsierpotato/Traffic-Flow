# Manual Geometry Annotation

Use this folder to draw per-sequence lane geometry for the 14 selected UA-DETRAC benchmark sequences.

## Files

- `geometry_editor.html` - local browser tool for drawing lane geometry.
- `sequences.json` - selected sequence manifest.
- `frames/<sequence>.jpg` - first frame for each selected sequence.

## Workflow

1. Open `benchmark/annotation/geometry_editor.html` in a browser.
2. Select one sequence.
3. Add one or more lanes.
4. For each lane, draw:
   - `valid_zone`: click polygon points, then press `Finish polygon`.
   - `counting_line`: click exactly two points.
   - `direction`: click start point then end point.
5. Press `Export JSON`.
6. Save the JSON as:

```text
benchmark/configs/geometry_manual/<sequence>.json
```

Repeat for all 14 sequences:

```text
MVI_20011
MVI_20012
MVI_20035
MVI_40241
MVI_40213
MVI_40752
MVI_40963
MVI_63553
MVI_41063
MVI_40892
MVI_39401
MVI_40793
MVI_40854
MVI_40761
```

After all files exist, regenerate derived counting GT using the manual geometry directory.

Note: `valid_zone` is exported as a closed polygon. The tool automatically appends the first point to the end of the polygon if needed. If the last drawn edge intersects the first drawn edge, the tool replaces the final point with that intersection before closing the polygon.
