# Guest Parent Start Fix (Pre Icarus v5.18)

Pre Icarus v5.18 fixes guest parent selection for career start.

## Problem

Guest parent cards could be selected in the library grid but did not appear in the top **Parent 2** setup slot. The run payload then treated the guest parent as a normal owned succession parent by sending its trained character id as `succession_trained_chara_id_2`.

For guest/rental parents, the game start payload needs the owned parent in the normal succession field and the guest parent in `rental_succession_trained_chara`.

## Fixed behavior

When selecting **1 owned parent + 1 guest parent**:

- Parent 1 displays the owned parent.
- Parent 2 displays the guest parent.
- The start payload sends:
  - `succession_trained_chara_id_1 = owned parent id`
  - `succession_trained_chara_id_2 = 0`
  - `rental_succession_trained_chara.viewer_id = guest viewer id`
  - `rental_succession_trained_chara.trained_chara_id = guest trained character id`

When selecting **2 owned parents**, the payload remains unchanged.

## Safety validation

The Run Career button is blocked if a selected guest parent is missing either the viewer id or trained character id needed by the start endpoint. The dashboard asks the user to refresh guest parents and select a full guest entry instead of sending a malformed request.
