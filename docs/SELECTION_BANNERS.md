# Team and hero selector headers

The original team header is assembled from two SSAD panes: a team-specific
label and a shared Japanese selection suffix sampled from the hero label's
atlas rectangle. The English atlas already contains complete phrases, so the
shared suffix added the end of **Select Hero** after **Select Team**.

The correction changes only KDATAPS3.CPK entry 32:

- Center the complete team label at x=271 instead of the old partial-label
  x=219 origin.
- Set the redundant suffix pane's opacity key to zero.

The hero selector uses one complete header sprite in entry 33. Its layout was
inspected and has no separate suffix pane. No header artwork is stretched or
changed by this correction. The CPK verifier confirms the other 161 entries
remain identical. The correction is installed for another in-game test;
neither selector is used as a README showcase until its appearance is checked.
