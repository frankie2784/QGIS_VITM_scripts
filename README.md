# QGIS_VITM_scripts
## Rapid Line Evaluation Branch

Idea for checking bus routes rapidly in GIS.

1. load in GTFS route information and extract route numbers (since route numbers aren't imported directly for some reason)
2. load in LIN file
3. Compare the termini on each line checking that a certain distance is not exceeded
4. Compare the matching lines on a point by point basis (probably along the GTFS since that should be mroe complex) making sure the nearest point on the other line doesn't exceed a certain distance
5. Spit out any routes that don't exist in both sets