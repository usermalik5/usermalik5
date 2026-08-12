# GeloTech scrcpy / phone-mirror guide

Read this file only when changing the phone-mirror subsystem.

## Scope

The Dashboard owns the native scrcpy mirror host. Mirror compatibility helpers
must remain isolated to mirror code. Do not use `sitecustomize.py`, import-time
patches, or navigation hooks to fix ordinary Dashboard/page behavior.

## Development checks

1. Test `python techtool.py` with a real supported Android device when possible.
2. Verify the mirror is embedded in the Dashboard phone screen.
3. Verify the mirror stops cleanly when leaving/stopping the feature.
4. Verify the Dashboard log console is restored after the mirror stops.
5. Test the packaged EXE separately when the build/spec changes.

## Failure reporting

Record whether a failure was observed with a real device, with scrcpy only,
or in a mocked/no-device environment. Do not claim a real-device fix from a
mocked test.

## Architecture rule

New mirror behavior belongs in the mirror subsystem. Do not add another global
runtime hook just because the packaged build behaves differently; first trace
the source execution path and the PyInstaller resource/spec path separately.
