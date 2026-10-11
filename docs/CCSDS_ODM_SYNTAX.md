
# **7 ORBIT DATA MESSAGE SYNTAX** 

## **7.1 OVERVIEW** 

This section details the syntax requirements for each of the Orbit Data Messages. 

## **7.2 GENERAL** 

The Orbit Data Messages (OPM, OMM, OEM, and OCM) shall observe the syntax described in 7.3 through 7.8. 

## **7.3 ODM LINES** 

**7.3.1** Each OPM, OMM, OEM, or OCM line shall be one of the following: 

- Header line; 

- Metadata line; 

   - Data line; 

   - Comment line; or 

- Blank line. 

**7.3.2** Each OPM, OMM, or OEM line must not exceed 254 ASCII characters and spaces (excluding line termination character[s]). 

**7.3.3** OCM lines may be of arbitrary length.  If exchange between the two parties requires a maximum line length, that limit should be mutually agreed upon between message exchange partners. 

**7.3.4** Only printable ASCII characters and blanks shall be used.  Control characters (such as TAB, etc.) shall not be used, except for the line termination characters specified below. 

**7.3.5** Blank lines may be used at any position within the file.  Blank lines shall have no assignable meaning and may be ignored. 

**7.3.6** The first header line must be the first non-blank line in the file. 

**7.3.7** All lines shall be terminated by a single Carriage Return or a single Line Feed, a Carriage Return/Line Feed pair, or a Line Feed/Carriage Return pair. 






## **7.4 ORBIT DATA MESSAGES IN ‘KEYWORD = VALUE NOTATION’ (I.E., NONXML) AND ORDER OF ASSIGNMENT STATEMENTS** 

**7.4.1** For the OPM and OMM, all header, metadata, and data lines shall use ‘keyword = value’ notation, abbreviated as KVN. 

**7.4.1.1** For the OEM, all header and metadata elements shall use KVN notation. 

**7.4.1.2** OEM ephemeris data lines shall not use KVN format; rather, the OEM ephemeris data line has a fixed structure containing seven required fields (epoch time, three position components, three velocity components), and three optional acceleration components.  (See 5.2.4.) 

**7.4.1.3** OEM covariance matrix epoch and covariance reference frame (if used) shall use KVN format.  The OEM covariance data lines shall not use KVN format; rather, the OEM covariance data line has a fixed structure containing from one to six required fields (a row from the 6x6 lower triangular form covariance matrix).  (See 5.2.5.) 

**7.4.1.4** For the OCM, all header and metadata elements shall use KVN notation. 

**7.4.1.5** OCM trajectory state time history data lines shall not use KVN format; rather, the structure of such OCM trajectory state time history data shall comprise a contiguous set of lines, with the values on each line separated by at least one white space character, and those values consisting of the time tag followed by the parameters corresponding to the selected orbit set (see TRAJ_TYPE, 6.2.5). 

**7.4.1.6** OCM covariance matrix epoch and covariance reference frame (if used) shall use KVN format.  The OCM covariance data lines shall not use KVN format; rather, OCM covariance time history data shall comprise a contiguous set of lines, with the values on each line separated by at least one white space character, and those values consisting of the time tag followed by the covariance matrix corresponding to the selected covariance type (see COV_TYPE, 6.2.7, particularly 6.2.7.11 through 6.2.7.13). 

**7.4.1.7** OCM maneuver data lines shall not use KVN format; rather, OCM maneuver data shall comprise a contiguous set of lines, the values on each line separated by at least one white space character, and with those values consisting of the specified maneuver parameters (see MAN_COMPOSITION, 6.2.8.14). 

**7.4.2** The keywords ‘COMMENT’, *‘_START’, and *‘_STOP’ are exceptions to the KVN syntax assignment. 

**7.4.3** Only a single ‘keyword = value’ assignment shall be made on a line. 

**7.4.4** Keywords must be uppercase and must not contain blanks. 

**7.4.5** Any white space immediately preceding or following the keyword shall not be significant. 






**7.4.6** Any white space immediately preceding or following the ‘equals’ sign shall not be significant. 

**7.4.7** Any white space immediately preceding the end of line shall not be significant. 

**7.4.8** The order of occurrence of mandatory and optional KVN assignments shall be fixed as shown in the tables in sections 3, 4, 5, and 6 that describe the OPM, OMM, OEM, and OCM keywords. 

## **7.5 VALUES** 

**7.5.1** A non-empty value field must be assigned to each mandatory keyword except for *‘_START’ and *‘_STOP’ keyword values. 

**7.5.2** Comments and free-text value fields may be in any case (or mix of case) desired by the user. 

**7.5.3** Apart from comments and free-text fields, normative text value fields shall be constructed using only exclusively all uppercase or exclusively all lowercase. 

**7.5.4** Integer values shall consist of a sequence of decimal digits with an optional leading sign (‘+’ or ‘-’).  If the sign is omitted, ‘+’ shall be assumed.  Leading zeroes may be used. The range of values that may be expressed as an integer is: 

-2,147,483,648 ≤ x ≤ +2,147,483,647  (i.e., -2<sup>31</sup> ≤ x ≤ 2<sup>31</sup> -1). 

- NOTE – The commas in the range of values above are thousands separators and are used only for readability. They should not appear in an actual message. 

**7.5.5** Non-integer numeric values may be expressed in either fixed-point or floating-point notation.  Both representations may be used within an OPM, OMM, OEM, or OCM. 

**7.5.6** Non-integer numeric values expressed in fixed-point notation shall consist of a sequence of decimal digits separated by a period as a decimal point indicator, with an optional leading sign (‘+’ or ‘-’).  If the sign is omitted, ‘+’ shall be assumed. Leading and trailing zeroes may be used.  At least one digit shall appear before and after a decimal point. The number of digits shall be 16 or fewer. 

**7.5.7** Non-integer numeric values expressed in floating point notation shall consist of a sign, a mantissa, an alphabetic character indicating the division between the mantissa and exponent, and an exponent, constructed according to the following rules: 

a) The sign may be ‘+’ or ‘-’.  If the sign is omitted, ‘+’ shall be assumed. 

- b) The mantissa must be a string of no more than 16 decimal digits with a decimal point (‘.’) in the second position of the ASCII string, separating the integer portion of the mantissa from the fractional part of the mantissa. 






- c) The character used to denote exponentiation shall be ‘E’ or ‘e’. If the character indicating the exponent and the following exponent are omitted, an exponent value of zero shall be assumed (essentially yielding a fixed-point value). 

- d) The exponent must be an integer and may have either a ‘+’ or ‘-’ sign (if the sign is omitted, then ‘+’ shall be assumed). 

- e) The maximum positive floating-point value is approximately 1.798E+308, with 16 significant decimal digits precision.  The minimum positive floating-point value is approximately 4.94E-324, with 16 significant decimal digits precision. 

**7.5.8** Blanks shall not be permitted within numeric values and time strings. 

**7.5.9** In value fields that are text, an underscore shall be equivalent to a single blank. Individual blanks shall be retained (shall be significant), but multiple contiguous blanks shall be equivalent to a single blank. 

**7.5.10** In value fields that represent an absolute time tag or epoch, times shall be given in one of the following two formats: 

YYYY-MM-DDThh:mm:ss[.d→d][Z] 

or 

YYYY-DDDThh:mm:ss[.d→d][Z], 

where ‘YYYY’ is the year; ‘MM’ is the two-digit month; ‘DD’ is the two-digit day; ‘DDD’ is the three-digit day of year; ‘T’ is constant; ‘hh:mm:ss[.d→d]’ is the time in hours, minutes, seconds, and optional fractional seconds; and ‘Z’ is an optional time code terminator (the only permitted value is ‘Z’ for Zulu, i.e., UTC).  As many ‘d’ characters to the right of the period as required may be used to obtain the required precision, up to the maximum allowed for a fixed-point number.  All fields shall have leading zeros.  (See reference [2], ASCII Time Code A or B.) 

- NOTE – During a leap second introduction, the value of the two-digit integer seconds (ss) field shall be ‘60’ as specified in reference [2]. 

**7.5.11** The time system for CREATION_DATE is UTC; for all other keywords representing times or epochs, the time system is determined by the TIME_SYSTEM metadata keyword. 

## **7.6 OCM VECTOR DATA TYPE** 

**7.6.1** Several OCM keywords may be set to values containing more than one number. Examples include DC_REF_DIR and DC_BODY_TRIGGER.  Such vectors shall be spacedelimited and provided serially on a single line following the equals ‘=’ sign, adhering to the requirements for ‘numeric values’ provided in the previous sections. 






## **7.7 UNITS IN THE ORBIT DATA MESSAGES** 

## **7.7.1 OPM/OMM UNITS** 

**7.7.1.1** For documentation purposes and clarity only, units may be included as ASCII text after a value in the OPM and OMM.  If units are displayed, they must exactly match the units (including lower/upper case) as specified in tables 3-3 and 4-3.  If units are displayed, then: 

- a) there must be at least one blank character between the value and the units text; 

- b) the units must be enclosed within square brackets (e.g., ‘[km]’); 

- c) combinations of units shall adhere to requirements listed in 1.5. 

**7.7.1.2** Some of the items in the applicable tables are dimensionless.  The table shows a unit value of ‘n/a’, which in this case means that there is no applicable units designator for these items (e.g., for ECCENTRICITY). 

**7.7.1.3** The notation ‘[n/a]’ shall not appear in an OPM or OMM. 

## **7.7.2 OEM UNITS** 

**7.7.2.1** In an OEM ephemeris data line, units shall be km, km/s, and km/s**2 for position, velocity, and acceleration components, respectively, but the units shall not be displayed. 

**7.7.2.2** In an OEM covariance matrix line, units shall be km**2, km**2/s, or km**2/s**2, depending on whether the element is computed from two position components, one position component and one velocity component, or two velocity components.  The units shall not be displayed. 

## **7.7.3 OCM UNITS** 

**7.7.3.1** Apart from trajectory state, covariance, and maneuver data lines, units of OCM keyword values shall correspond to the normative ‘Units’ column of the accompanying Keyword Value Tables (i.e., tables 6-3 through 6-12) for each section definition. 

- NOTE – The units used throughout the OCM are generally a combination of kilometers for distance and seconds for time (e.g., km/s for velocity, km/s**2 for acceleration, and so forth).  Mass is in kilograms, and force is in Newtons. 

**7.7.3.2** The units of orbit time state history data lines, when present, shall adhere to the specified units for trajectory states as provided in the SANA Registry (reference [11]) for Orbital Elements (annex B,  subsection B7). 






**7.7.3.3** The units of covariance time history data lines, when present, shall adhere to the specified units for covariance data as provided in the SANA Registry (reference [11]) for Orbital Elements (annex B,  subsection B7) and Additional Covariance Representations (annex B,  subsection B8). 

**7.7.3.4** The units of maneuver time history data lines, when present, shall adhere to the specified units for maneuver lines as provided in table 6-8 and table 6-9. 

**7.7.3.5** For OCM keywords used to convey multipartite trajectory state, covariance, or maneuver data lines, units may accompany these data lines via the TRAJ_UNITS, COV_UNITS, and MAN_UNITS keywords, respectively. Units shall not be displayed in OCM trajectory state, covariance, or maneuver data lines themselves. 

**7.7.3.6** For OCM keywords that are not used to convey multipartite trajectory state, covariance, or maneuver data lines, units may be included as ASCII text after a value in the OCM for documentation purposes and clarity only. If units are displayed, then: 

- a) there must be at least one blank character between the value and the units text; 

- b) the units must be enclosed within square brackets (e.g., ‘[m]’); 

- c) combinations of units shall adhere to requirements listed in 1.5. 

**7.7.3.7** Some of the items in the applicable tables are dimensionless.  The table shows a unit value of ‘n/a’, which in this case means that there is no applicable units designator for these items (e.g., for ECCENTRICITY) and no units displayed. 

## **7.8 COMMENTS IN THE ORBIT DATA MESSAGES** 

**7.8.1** There are certain pieces of information that provide clarity and remove ambiguity about the interpretation of the information in a file yet are not standardized so as to fit cleanly into the ‘keyword = value’ paradigm.  Rather than force the information to fit into a space limited to one line, the ODM producer should put further specifications and information into comments.  Static information should be separately shared and/or mutually agreed upon between message exchange partners outside of the ODM. 

**7.8.2** Comments may be used to provide provenance information or to help describe dynamical events or other pertinent information associated with the data.  This additional information is intended to aid in consistency checks and elaboration when needed but shall not be required for successful processing of a file. 

**7.8.3** For the OPM, OMM, OEM, and OCM, comment lines shall be optional. 

**7.8.4** Comment text may be in any case (or mix of case) desired by the user. 






**7.8.5** All comment lines shall begin with the ‘COMMENT’ keyword followed by at least one space.  This keyword must appear on every comment line, not just the first such line. The remainder of the line shall be the comment value.  White space shall be retained (shall be significant) in comment values. 

**7.8.6** Placement of comments shall be as specified in the tables in sections 3, 4, 5, and 6 that describe the OPM, OMM, OEM, and OCM keywords. 

**7.8.7** Comments in the OPM may appear in the OPM Header immediately after the ‘CCSDS_OPM_VERS’ keyword, at the very beginning of the OPM Metadata section, and at the beginning of a logical block in the OPM Data section.  Comments must not appear between the components of any logical block in the OPM Data section. 

NOTE – The logical blocks in the OPM Data section are indicated in table 3-3. 

**7.8.8** Comments in the OMM may appear in the OMM Header immediately after the ‘CCSDS_OMM_VERS’ keyword, at the very beginning of the OMM Metadata section, and at the beginning of a logical block in the OMM Data section.  Comments must not appear between the components of any logical block in the OMM Data section. 

NOTE – The logical blocks in the OMM Data section are indicated in table 4-3. 

**7.8.9** Comments in the OEM may appear in the OEM Header immediately after the ‘CCSDS_OEM_VERS’ keyword, at the very beginning of the OEM Metadata section (after the ‘META_START’ keyword), at the beginning of the OEM Ephemeris Data Section, and at the beginning of the OEM Covariance Data section (after the ‘COV_START’ keyword). Comment lines must not appear within any block of ephemeris lines or covariance matrix lines. 

**7.8.10** Comments may appear in all logical blocks of the OCM, but only at the positions shown in the defining tables (generally at the top of each section, following the *_START section delimiting keyword). 

**7.8.11** Extensive comments in an ODM are recommended in cases when that content is germane to the message and changes from message to message. 

- **7.8.12** The following comments should be provided: 

   - a) Information regarding the genesis, history, interpretation, intended use, etc., of the state vector, spacecraft, maneuver, or ephemeris that may be of use to the receiver of the OPM, OMM, OEM, or OCM: 

COMMENT Source: File created by JPL Multi-Mission Navigation Team as part COMMENT of Launch Operations Readiness Test held on 20 April 2001. 






- b) Natural body ephemeris information:  When the Earth is not the center of motion, the ephemerides of the planets, satellites, asteroids, and/or comets (including associated constants) consistent with the ODM should be identified so that the recipient can, in a consistent manner, make computations involving other centers: 

COMMENT Based on latest orbit solution which includes observations COMMENT through 2000-May-15 relative to planetary ephemeris DE-0405. 

- c) OEM accuracy vs. efficiency:  If the covariance data section of the OEM is not utilized, the producer of an OEM should report in comment lines what the expected accuracy of the ephemeris is, so the user can smooth or otherwise compress the data without affecting the accuracy of the trajectory.  The OEM producer also should strive to achieve not only the best accuracy possible, considering prediction errors, but also consider the efficiency of the trajectory representation (e.g., step sizes of fractional seconds between ephemeris lines may be necessary for precision scientific reconstruction of an orbit, but are excessive from the standpoint of antenna pointing predicts generation). 

## **7.9 ORBIT DATA MESSAGE KEYWORDS** 

## **7.9.1 VERSION KEYWORDS** 

The Header of the OPM, OMM, OEM, and OCM shall provide a CCSDS Orbit Data Message version number that identifies the format version; this is included to anticipate future changes. The version keywords for the OPM, OMM, OEM, and OCM shall be CCSDS_OPM_VERS, CCSDS_OMM_VERS, CCSDS_OEM_VERS, and CCSDS_OCM_VERS, respectively.  The value shall have the form of ‘x.y’, where ‘y’ shall be incremented for corrections and minor changes, and ‘x’ shall be incremented for major changes.  Version x.0 shall be reserved for versions accepted by the CCSDS as an official Recommended Standard (‘Blue Book’).  Testing shall be conducted using OPM, OMM, OEM, and OCM version numbers less than 1.0 (e.g., 0.x).  The specific OPM, OMM, OEM, and OCM version numbers to be used should be mutually agreed between message exchange partners.  The following version numbers are supported (Blue Book) or have been supported in the past (Silver Book): 

|**Version Keyword**|**Version Number**|**Applicable Recommendation**|
|---|---|---|
|CCSDS_OPM_VERS|1.0|Silver Book 1.0,09/2004|
|CCSDS_OPM_VERS|2.0|Silver Book 2.0,11/2009|
|CCSDS_OPM_VERS|3.0|Blue Book 3.0(this document)|
|CCSDS_OMM_VERS|2.0|Silver Book 2.0,11/2009|
|CCSDS_OMM_VERS|3.0|Blue Book 3.0(this document)|
|CCSDS_OEM_VERS|1.0|Silver Book 1.0,09/2004|
|CCSDS_OEM_VERS|2.0|Silver Book 2.0,11/2009|
|CCSDS_OEM_VERS|3.0|Blue Book 3.0(this document)|
|CCSDS_OCM_VERS|3.0|Blue Book 3.0(this document)|








## **7.9.2 GENERAL KEYWORDS** 

**7.9.2.1** Only those keywords shown in tables 3-1, 3-2, and 3-3 shall be used in an OPM. Some keywords represent mandatory items, and some are optional.  KVN assignments representing optional items may be omitted. 

**7.9.2.2** Only those keywords shown in tables 4-1, 4-2, and 4-3 shall be used in an OMM. Some keywords represent mandatory items, and some are optional.  KVN assignments representing optional items may be omitted. 

**7.9.2.3** Only those keywords shown in tables 5-2 and 5-3 shall be used in an OEM.  Some keywords represent mandatory items, and some are optional.  KVN assignments representing optional items may be omitted. 

**7.9.2.4** Only those keywords shown in tables 6-3 through 6-12 shall be used in an OCM. Some keywords represent mandatory items, and some are optional. KVN assignments representing optional items may be omitted. 

## **7.10 VALIDATION AND INGEST OF KVN CONTENT VIA REGULAR EXPRESSIONS (OR ‘REGEX’)** 

## **7.10.1 BENEFITS OF USING REGULAR EXPRESSIONS WITH THE ODM** 

Unlike the schema validation feature native to XML versions of this message as described in section 8, the KVN version of this message does not natively support such validations of KVN content.  To accomplish validation and ingest of KVN versions of the ODM, the use of Regular Expressions (referred to as ‘Regex’) is strongly encouraged where possible.  Most programming languages support the Regex feature, and Regex offers a detailed and rigorous way to ensure proper validation, interpretation, and conformance to Orbit Data Message content. 

## **7.10.2 SAMPLE REGULAR EXPRESSIONS FOR CCSDS MESSAGES** 

To facilitate the use of Regular Expressions when processing CCSDS Navigation Messages, informative annex F, subsection F6 provides sample Regex patterns to rigorously match a variety of common KVN sequences. 





