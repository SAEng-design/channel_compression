# Channel Section — Compressive Resistance

A structural design tool for ViKO Consulting Engineers that calculates the design compressive resistance of **Parallel Flange Channels (PFC)** and **Taper Flange Channels (TFC)** under axial load, in accordance with **SANS 10162-1**.

---

## Overview

This app calculates the factored compressive resistance `Cr` of channel sections based on the design clauses of SANS 10162-1, including:

- Section classification per Cl. 11
- Slenderness ratio check per Cl. 10.4.2.1
- Flexural and **flexural-torsional** buckling per Cl. 13.3.2
- Effective area reduction for Class 4 sections per Cl. 13.3.3

In addition to the design check, the app includes a **Section Optimiser** tab that finds the lightest passing PFC and TFC for a given factored load and effective length set.

The result is presented as a single governing `Cr` value, with a full breakdown of intermediate calculations.

---

## Why Channels Are Different from H/I-Sections

Channels are **singly symmetric** (symmetric about the x-axis only), which means the **shear centre does not coincide with the centroid** of the section. This has a significant consequence for compression design:

- For a doubly symmetric H or I-section, pure flexural buckling about the weak axis almost always governs.
- For a channel, **flexural-torsional buckling** (a coupled mode that combines strong-axis flexure with torsion) often governs instead — even when the section appears to be braced about its weak axis.

The shear centre offset distance `x₀ = aₓ` is read directly from the CSV section database. The app then explicitly calculates the flexural-torsional buckling stress `f_exz` and includes it in the check for the governing elastic buckling stress.

---

## How the App Works

### 1. Section Selection

The app reads section properties directly from two CSV databases sourced from the SAISC Red Book:

- `parallel_flange_channels.csv` — PFC sections (modern parallel-flange profiles)
- `taper_flange_channels.csv` — TFC sections (traditional tapered-flange profiles)

Users select the channel type (PFC or TFC) and the designation from a dropdown. All geometric and sectional properties (`A`, `Ix`, `Iy`, `rx`, `ry`, `J`, `Cw`, `aₓ`, etc.) are pulled automatically. For TFCs, the additional properties `b₁` (flat flange width) and `β` (taper angle) are also loaded.

### 2. Material Selection

Users choose from standard steel grades or define a custom grade:

- **S355JR** — fy = 355 MPa
- **S275JR** — fy = 275 MPa
- **S235JR** — fy = 235 MPa
- **Custom** — user-defined fy between 200 and 700 MPa

For standard grades with flange thickness `tf > 16 mm`, the app automatically reduces fy per SANS specification (e.g., S355 → 345). This adjustment is applied per-section, so the optimiser correctly uses the right fy for each candidate.

### 3. Manufacturing Type

The user selects the manufacturing process which sets the parameter `n` in Eq. 4.24:

- **Hot-rolled** — `n = 1.34`
- **Welded stress-relieved** — `n = 2.24`

### 4. Effective Lengths

Three independent effective lengths are entered:

- `KLx` — about the strong (x) axis
- `KLy` — about the weak (y) axis
- `KLz` — torsional buckling length

Setting any value to `0` indicates that axis is laterally restrained and excluded from the buckling check.

---

## Calculation Procedure

### Step 1: Section Classification (Cl. 11)

The flange and web are classified separately as **Class 3 or better** or **Class 4 (slender)**:

- **Flange** (outstand supported on one edge, attached to the web): `b_outstand/tf ≤ 200/√fy`
  - For **PFC**: outstand = `b` (the full flange width — the channel flange is attached to the web on one side only)
  - For **TFC**: outstand = `b₁` (the flat portion of the tapered flange)
- **Web** (supported on both edges): `hw/tw ≤ 670/√fy`

If either element exceeds its limit, the overall section is classified as **Class 4** and an effective area calculation is required.

> **Note:** Unlike H or I-sections, the channel flange outstand is the full flange width (not b/2), because the flange is attached to the web on only one side.

### Step 2: Slenderness Check (Cl. 10.4.2.1)

Both `KLx/rx` and `KLy/ry` must not exceed **200**. The app flags any axis that exceeds this limit.

### Step 3: Elastic Buckling Stresses

Four elastic buckling stresses are calculated:

- **Flexural about x-axis:** `f_ex = π²E / (KLx/rx)²`
- **Flexural about y-axis:** `f_ey = π²E / (KLy/ry)²`
- **Pure torsional about z-axis:** `f_ez = [π²E·Cw/(KLz)² + GJ] / (A·r₀²)`
- **Flexural-torsional (combined x + z):** see below

Where the polar radius of gyration about the shear centre is:

```
r₀² = x₀² + y₀² + rx² + ry²
```

For a singly-symmetric channel, `x₀ = aₓ` (read from the CSV) and `y₀ = 0`.

The flexural-torsional buckling stress per Cl. 13.3.2(b) is:

```
f_exz = [(f_ex + f_ez) / (2Ω)] × [1 - √(1 - 4·f_ex·f_ez·Ω / (f_ex + f_ez)²)]
```

Where `Ω = 1 - (x₀² + y₀²) / r₀²`.

The governing elastic buckling stress for a channel is:

```
f_e = min(f_ey, f_exz)
```

> **Important:** For channels, `f_ex` (pure flexural buckling about the strong axis) does **not** govern alone — it is always coupled with torsion through `f_exz`. The two competing modes are weak-axis flexural buckling (`f_ey`) and the combined flexural-torsional mode (`f_exz`).

### Step 4: Effective Area for Class 4 Sections (Cl. 13.3.3)

If the section is Class 4, the effective area is calculated using:

```
W = b/t
W_lim = 0.644 × √(k·E/f)
b_eff = 0.95t·√(k·E/f) × (1 - 0.208/W × √(k·E/f))
```

Where:
- `k = 0.43` for elements supported on one edge (flanges)
- `k = 4.0` for elements supported on both edges (webs)
- `f` is the calculated compressive stress in the element, taken as `f = fy·(1 + λ^(2n))^(-1/n)`, capped at fy

The reduction is applied **only to elements that are individually Class 4**:
- Flange reduction is multiplied by **2** (2 outstand flanges, top and bottom — note this differs from H/I-sections, which have 4 outstands)
- Web reduction is applied once (single element)

### Step 5: Compressive Resistance (Cl. 13.3.1, Eq. 4.24)

The factored compressive resistance is calculated as:

```
Cr = φ·A_eff·fy·(1 + λ^(2n))^(-1/n)
```

Where:
- `φ = 0.90` (resistance factor)
- `A_eff` = gross area `A` for non-Class 4 sections, or reduced effective area for Class 4
- `λ = √(fy/f_e)` (non-dimensional slenderness ratio)
- `n` = 1.34 (hot-rolled) or 2.24 (welded stress-relieved)

---

## Section Optimiser

The second tab of the app provides a **Section Optimiser** that finds the lightest passing PFC and TFC for the user's design conditions.

### How It Works

1. The user enters a target factored load `C*` in the optimiser tab.
2. The app sweeps through every section in both the PFC and TFC databases.
3. For each section, the full Cr calculation (Steps 1–5) is performed using the same `KLx`, `KLy`, `KLz`, steel grade, and manufacturing type set in the sidebar.
4. The lightest section in each family that satisfies both `Cr ≥ C*` AND the slenderness limit is reported.

### What the Optimiser Returns

- The lightest passing **PFC** and the lightest passing **TFC**, side-by-side, with mass, Cr, utilisation, governing buckling mode, and Class 4 status.
- A summary verdict identifying which family wins overall and by how much (e.g., *"TFC saves 3.2 kg/m vs the lightest PFC"*).
- An expandable full table showing every section evaluated, sorted by mass within each family — useful for the QC reviewer to verify why a particular section was selected.
- If no section in a family passes, the app reports how short the heaviest section came (a useful sizing signal).

### Limitations of the Optimiser

- The optimiser uses **the same KL values across all candidate sections**. This is correct for typical design where bracing is fixed by the structure, but the user should be aware that K factors may vary slightly between sections in some configurations.
- The optimiser does **not** account for connection geometry, availability, or detailing constraints — only the SANS 10162-1 compression check.
- Only sections in the loaded CSV databases are considered. To extend the database, add new rows to the relevant CSV.

---

## Output

The app displays (across two tabs):

**Design Check tab:**

1. **Section properties summary** — all dimensions and section properties in one panel
2. **Headline result** — `Cr` in kN, governing buckling mode, utilisation ratio, and PASS/FAIL status (if a factored load is provided)
3. **Detailed calculation breakdown** — every intermediate value from classification through to final `Cr`, including the full flexural-torsional derivation (`r₀²`, `Ω`, `f_exz`)
4. **Buckling mode comparison table** — `Cr` if each individual buckling mode were to govern, with the actual governing mode marked with a star (★)

**Section Optimiser tab:**

1. **Target load input** with sidebar settings echoed for clarity
2. **Side-by-side PFC and TFC results** showing the lightest passing section in each family
3. **Summary verdict** highlighting the lighter overall option and the mass saving
4. **Expandable full evaluation table** for transparency and QC

---

## Important Notes & Limitations

- ⚠️ **For Class 4 sections, always cross-check the `Cr` value against the SAISC Red Book.** The effective area calculation per Cl. 13.3.3 can be sensitive to the assumed value of `f`, and minor differences may occur compared to other reference tools.
- The app uses `aₓ` from the CSV directly as the shear centre offset `x₀`. This convention has been verified against the SAISC Red Book worked Example E4.5 (PC 180×70: `aₓ = 43.5 mm`).
- For channels, **flexural-torsional buckling frequently governs** — particularly for shorter columns or sections with smaller `Cw`. The app explicitly identifies which mode governs in the headline result.
- The factored material reduction for `tf > 16 mm` only applies to standard steel grades — custom grades require the user to enter the correct `fy` directly.
- The resistance factor `φ = 0.90` is fixed in line with SANS 10162-1 Cl. 13.3.1.
- The optimiser inherits the user's effective lengths from the sidebar — **always confirm KLx, KLy, KLz are correct for the design before relying on the optimiser output.**

---

## Verification

The app has been verified against:

- **Worked Example E4.5 (SAISC Red Book)** — PC 180×70, S355JR (fy = 350 MPa used in book), KL = 2000 mm, hot-rolled
  - Expected: `Cr = 402 kN`
  - App result: `Cr = 401 kN` ✅ (0.25% difference attributable to book's λ rounding)
  - All intermediate values match: `f_ex = 2488` (book 2482), `f_ey = 235` (book 235), `f_ez = 481` (book 481), `Ω = 0.745` (book 0.745), `f_exz = 455` (book 455)

---

## Tech Stack

- **Python 3** with `pandas` for data handling and `streamlit` for the web interface
- **Hosted on:** [Streamlit Community Cloud](https://share.streamlit.io)
- **Section database:** `parallel_flange_channels.csv` and `taper_flange_channels.csv` (extracted from SAISC Red Book)

---

## ⚠️ Disclaimer

This application is provided as a **design aid only** and does not replace the engineer's professional judgment or responsibility.

By using this app, the user accepts the following:

- The user is solely responsible for verifying all input values, intermediate calculations, and final results before using them in any structural design or for any project deliverable.
- All output should be **independently checked** against the relevant code (SANS 10162-1) and reference tools such as the SAISC Red Book or hand calculations, particularly for Class 4 sections, unusual configurations, or critical applications.
- ViKO Consulting Engineers, Jandre Nel, and any associated parties accept **no liability** for errors, omissions, misinterpretations, or any direct or indirect loss, damage, or harm arising from the use of this app or reliance on its results.
- This app is intended for use by qualified structural engineers who understand the underlying theory, code provisions, and limitations of the calculations performed.
- The app is provided "as is" without any warranty of accuracy, completeness, or fitness for a particular purpose.
- **The Section Optimiser is a sizing aid only** — the engineer must verify that the recommended section is suitable for the full design intent, including connections, fabrication, availability, and any other applicable load combinations.

**The engineer using this app remains fully responsible for the integrity, safety, and code compliance of any design produced.**

---

## About

Developed by **ViKO Consulting Engineers** as part of the internal Engineering Design Tools suite.

For questions, bug reports, or feature requests, please use the GitHub Issues tab.

---

*ViKO Consulting Engineers |
Jandre Nel 081 756 1292*
