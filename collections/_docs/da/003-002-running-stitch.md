---
title: "Running Stitch"
permalink: /da/docs/stitches/running-stitch/
excerpt: ""
last_modified_at: 2019-11-11
toc: true
---
## Hvad det er

[![Running Stitch Butterfly](/assets/images/docs/running-stitch.jpg){: width="200x"}](/assets/images/docs/running-stitch.svg){: title="Download SVG File" .align-left download="running-stitch.svg" }

"Running stitch" producerer en serie af små sting, som følger en linje eller en kurve.

![Running Stitch Detail](/assets/images/docs/running-stitch-detail.jpg)

## Hvordan bruge running stitch
Running stitch kan blive dannet ved at vælge en prikket linje på en path. Enhver type af prikket linjer vil kunne bruges og stegens bredde er ikke relevant.


![Running Stitch Dashes](/assets/images/docs/running-stitch-dashes.jpg){: .align-left style="padding: 5px"}
Vælg linjen og gå til `Object > Fill and Stroke...` 
Vælg en af de prikkede linjer i `Stroke style` fanen.

Åbne [`Extensions > Ink/Stitch  > Params`](/docs/params/#stroke-params) for at ændre parameterne efter dine behov.

Den retning, som linjen vil blive syet er afhængig af "path direction". Hvis du ønsker at bytte om på start- og slut-punkterne, så vælg `Path > Reverse`.

**Info:** 
For at undgå runde hjørner, så vil der blive lagt til en ekstra node (dv. et ekstra sting) i alle skarpe hjørner.
{: .notice--info style="clear: both;" }

## Sample Files Including Running Stitch
{% include tutorials/tutorial_list key="stitch-type" value="Running Stitch" %}
