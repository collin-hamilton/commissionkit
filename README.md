# commissionkit

commissionkit turns an I/O list into a guided checkout and a portable evidence report. it is designed for the part of commissioning where every field device has to be observed in both states and every result needs a name, time and reason.

the included demo uses a simulated adapter. it produces the same report structure without connecting to a controller.

## features

- imports input and output points from a plain csv file.
- verifies configured off and on values instead of assuming every point is boolean.
- records pass, fail or skipped with operator, utc timestamp and note.
- requires an explicit session token before any output exercise.
- refuses to exercise every point marked safety-related.
- returns outputs to their configured off state after a test.
- produces a self-contained html report with an evidence hash.
- keeps plc communication behind a small read/write adapter.

## quick start

```sh
python -m venv .venv
source .venv/bin/activate
python -m pip install -e .
commissionkit examples/io-list.csv --operator "collin hamilton"
```

open `commissionkit-report.html` after the run. the example passes three simulated points and skips the safety contactor.

## I/O list

```csv
tag,direction,description,off_value,on_value,safety_related
PE101,input,infeed photoeye,false,true,false
SOL101,output,reject solenoid,false,true,false
K1,output,safety contactor,false,true,true
```

inputs are observed by the commissioning operator. standard outputs may be exercised only when output writes were enabled at session creation and the exact session token is supplied. safety-related outputs are never sent to the adapter.

## running tests

```sh
python -m unittest discover -s tests -v
```

the tests cover state comparison, output confirmation, safe return-to-off behavior, duplicate tags and the safety-output prohibition.

## important limitation

an html report is not proof that a machine is safe or ready for production. use the approved electrical, controls and safety-validation procedures for the actual installation. commissionkit deliberately prevents automated safety-output tests because those procedures require independent authority and evidence.

