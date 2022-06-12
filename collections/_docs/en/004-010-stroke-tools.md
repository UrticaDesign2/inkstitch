---
title: "Tools: Stroke"
permalink: /docs/stroke-tools/
excerpt: ""
last_modified_at: 2022-05-21
toc: true
---
## Autoroute Running Stitch

{% include upcoming_release.html %}

Auto-Route Running Stitch..

This tool will **replace** your set of running stitches  with a new set of running stitches in logical stitching order avoiding as many jumps as possible . Under-pathing  will be added as necessary  . The resulting running stitches will retain all of the parameters you had set on the original stitches including stitch length, number of repeats, bean stitch number of repeats, etc. Underpaths will only retain the stitch length, but will be set to only one  repeat and no bean stitch number of repeats.

### Usage
- Select all the running stitches (prepared with parameters)that you wish to organize
- Run `Extensions > Ink/Stitch > Tools : Stroke > Auto-Route Running stitch...`
- Enable desired options and click apply

Tip: By default, it will choose the left-most extreme node as the starting point and the right-most extreme node  as the ending point (even if these are not terminal nodes). You can override this by attaching the "Auto-route running stitch starting/ending position" commands.


### Options
- Enable **Add nodes at intersections** will normally yield a better routing as under-paths will preferably start/end at intersections and terminal nodes.  You should only disable this option if you have manually added nodes where you want the paths to be split.
- Enable **Trim jump stitches** to use trims instead of jump stitches. Trim commands are added to the SVG, so you can modify/delete as you see fit.
- Enable **Preserve order of running stitches** if you prefer to keep your former order. 
