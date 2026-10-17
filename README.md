# Usage

## 1. Generate the TSV file

Run:

```bash
python3 sort.py
```

This generates the TSV file required by the Turing Machine simulator.

## 2. Upload the TSV file

Go to the Turing Machine simulator:

https://edstem.org/au/courses/38542/lessons/118243/slides/836183

Upload the generated TSV file.

## 3. Enter an input

Enter an input such as:

```text
[3A7F00C29B14E58D,3A7F00C29B14E58E,F000000000000000]
```

The input can contain any number of elements.

Each element must:

- Be exactly 16 characters long.
- Contain only hexadecimal characters `0-9` and `A-F`.

Click **Load Machine**, then click **Run**.

## 4. Record the results

After the machine finishes running, manually enter the results into `test.json`.

Use the following format:

```json
"2": {
    "input": "[3A7F00C29B14E58D,3A7F00C29B14E58E,F000000000000000]",
    "accepted": true,
    "step count": 817,
    "write complexity": 68,
    "space complexity": 52,
    "head position": 0,
    "comments": ""
},
```

Here, `"2"` is the test case number. Increment the test case number for each new test.