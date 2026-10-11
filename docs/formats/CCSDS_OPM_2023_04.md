

# **3 ORBIT PARAMETER MESSAGE** 

## **3.1 GENERAL** 

**3.1.1** Orbit information may be exchanged between two participants by sending a state vector (see reference [H1]) for a specified epoch using an OPM.  The message recipient must have an orbit propagator available that is able to propagate the OPM state vector to compute the orbit at other desired epochs.  For this propagation, additional ancillary information (spacecraft properties such as mass, area, and maneuver planning data, if applicable) may be included with the message. 

**3.1.2** Osculating Keplerian elements and the Gravitational Coefficient may be included in the OPM in addition to the Cartesian state to aid the message recipient in performing consistency checks.  If any Keplerian element is included, the entire set of elements must be provided. 

**3.1.3** If participants wish to exchange mean element information, then the OMM or OCM should be the selected message type (see sections 4 and 6.) 

- **3.1.4** The use of the OPM is best applicable under the following conditions: 

   - a) an orbit propagator consistent with the models used to develop the orbit data should be available at the receiver’s site. 

   - b) the receiver’s modeling of gravitational forces, solar radiation pressure, atmospheric drag, and thrust phases (see reference [H1]) should fulfill accuracy requirements established between the exchange partners. 

- **3.1.5** The OPM shall be a plain text file consisting of orbit data for a single object. 

- NOTE – A sequence of OPMs for either a single object or for multiple objects can be aggregated into a single NDM XML file as described in 8.12 and shown in annex G. 

**3.1.6** The OPM file-naming scheme should be mutually agreed between message exchange partners. 

**3.1.7** The method of exchanging OPMs should be mutually agreed between message exchange partners. 

## NOTES 

- 1 Detailed syntax rules for the OPM are specified in section 7. 

- 2 Example OPMs and associated supplementary (non-normative) information are provided in annex G. 







## **3.2 OPM CONTENT/STRUCTURE** 

## **3.2.1 GENERAL** 

The OPM shall be represented as a combination of the following: 

- a) a header; 

- b) metadata (data about data); 

- c) data; and 

- d) optional comments (explanatory information). 

## **3.2.2 OPM HEADER** 

- **3.2.2.1** Table 3-1 specifies for each header item: 

   - a) the keyword to be used; 

   - b) a short description of the item; 

   - c) examples of allowed values; and 

   - d) whether the item is Mandatory (M), Optional (O), or Conditional (C).  Conditional indicates that the item is mandatory if specified conditions are met (e.g., providing _all_ covariance matrix elements if _any_ are provided). 

- **3.2.2.2** Only those keywords shown in table 3-1 shall be used in an OPM header. 







**Table 3-1:  OPM Header** 

|**Keyword**|**Description**|**Examples of Values**|**M/O/C**|
|---|---|---|---|
|CCSDS_OPM_VERS|Format version in the form of ‘x.y’, where<br>‘y’ is incremented for corrections and minor<br>changes, and ‘x’ is incremented for major<br>changes.|3.0|M|
|COMMENT|Comments (allowed in the OPM Header<br>only immediately after the OPM version<br>number).(See  7.8 for formattingrules.)|This is a comment|O|
|CLASSIFICATION|User-defined free-text message<br>classification/caveats of this OPM.  It is<br>recommended that selected values be pre-<br>coordinated between exchanging entities by<br>mutual agreement.|SBU<br>'Operator-proprietary<br>data; secondary<br>distribution not<br>permitted'|O|
|CREATION_DATE|File creation date/time in UTC.  (For format<br>specification,see 7.5.10.)|2001-11-06T11:17:33<br>2002-204T15:56:23Z|M|
|ORIGINATOR|Creating agency or operator.  Select from the<br>accepted set of values indicated in annex B,<br>subsection B1 from the ‘Abbreviation’<br>column (when present), or the ‘Name’ column<br>when an Abbreviation column is not<br>populated.  If desired organization is not<br>listed there, follow procedures to request that<br>originator be added to SANA registry.|CNES, ESOC, GSFC, GSOC,<br>JPL, JAXA, INTELSAT,<br>USAF, INMARSAT|M|
|MESSAGE_ID|ID that uniquely identifies a message from a<br>given originator. The format and content of<br>the message identifier value are at the<br>discretion of the originator.|OPM 201113719185<br>ABC-12_34|O|



## **3.2.3 OPM METADATA** 

Table 3-2 specifies for each metadata item: 

   - a) the keyword to be used; 

   - b) a short description of the item; 

   - c) examples of allowed values; and 

   - d) whether the item is Mandatory (M), Optional (O), or Conditional (C).  Conditional indicates that the item is mandatory if specified conditions are met (e.g., providing _all_ covariance matrix elements if _any_ are provided). 

- **3.2.3.1** Only those keywords shown in table 3-2 shall be used in OPM metadata. 

- NOTE – For some keywords (OBJECT_NAME, OBJECT_ID) there are no definitive lists of authorized values maintained by a control authority; references [3] and [11] and the organizations provided on the SANA Registry (annex B, subsection B1) are the best known sources for authorized values to date.  (For the TIME_SYSTEM keyword, see annex B, subsection B3, for guidance and a link to the approved set of values.) 







**Table 3-2:  OPM Metadata** 

|**Keyword**|**Description**|**Examples of Values**|**M/O/C**|
|---|---|---|---|
|COMMENT|Comments (allowed at the beginning of the<br>OPM Metadata).  (See 7.8 for formatting<br>rules.)|This is a comment|O|
|OBJECT_NAME|Spacecraft name for which orbit state data is<br>provided.  While there is no CCSDS-based<br>restriction on the value for this keyword, it is<br>recommended to use names from the UN Office<br>of Outer Space Affairs designator index<br>(reference [3], which include Object name and<br>international designator of the participant).  If<br>OBJECT_NAME is not listed in reference [3] or<br>the content is either unknown or cannot be<br>disclosed, the value should be set to<br>UNKNOWN.|EUTELSAT W1<br>MARS PATHFINDER<br>STS 106<br>NEAR<br>UNKNOWN|M|
|OBJECT_ID|Object identifier of the object for which orbit<br>state data is provided.  While there is no<br>CCSDS-based restriction on the value for this<br>keyword, it is recommended to use the<br>international spacecraft designator as<br>published in the UN Office of Outer Space<br>Affairs designator index (reference [3]).<br>Recommended values have the format YYYY-<br>NNNP{PP}, where:<br>YYYY = Year of launch.<br>NNN<br>= Three-digit serial number of launch<br>in year YYYY (with leading zeros).<br>P{PP} = At least one capital letter for the<br>identification of the part brought<br>into space by the launch.<br>If the asset is not listed in reference [3], the<br>UN Office of Outer Space Affairs designator<br>index format is not used, or the content is<br>either unknown or cannot be disclosed, the<br>value should be set to UNKNOWN.|<br> <br> <br>2000-052A<br>1996-068A<br>2000-053A<br>1996-008A<br>UNKNOWN|M|
|CENTER_NAME|**Origin of the OPM reference frame**, which<br>shall be a natural solar system body (planets,<br>asteroids, comets, and natural satellites),<br>including any planet barycenter or the solar<br>system barycenter.  Natural bodies shall be<br>selected from the accepted set of values<br>indicated in annex B, subsection B2.|EARTH<br>EARTH BARYCENTER<br>MOON<br>SOLAR SYSTEM BARYCENTER<br>SUN<br>JUPITER BARYCENTER<br>STS 106<br>EROS|M|
|REF_FRAME|Reference frame in which the state vector and<br>optional Keplerian element data are given.<br>Use of values other than those in 3.2.3.3 should<br>be documented in an ICD.|ICRF<br>ITRF2000<br>EME2000<br>TEME|M|
|REF_FRAME_EPOCH|Epoch of reference frame, if not intrinsic to the<br>definition of the reference frame.  (See 7.5.10<br>for formattingrules.)|2001-11-06T11:17:33<br>2002-204T15:56:23Z|C|
|TIME_SYSTEM|Time system used for state vector, maneuver,<br>and covariance data.  Use of values other than<br>those in 3.2.3.2 should be documented in an<br>ICD.|UTC, TAI, TT, GPS, TDB,<br>TCB|M|









## **3.2.3.2** Values for the TIME_SYSTEM keyword should be selected from the following set: 

|**Time System Value**|**Meaning**|
|---|---|
|GMST|Greenwich Mean Sidereal Time|
|GPS|Global PositioningSystem|
|MET|Mission Elapsed Time (note)|
|MRT|Mission Relative Time (note)|
|SCLK|Spacecraft Clock (receiver) (requires rules for interpretation in<br>ICD)|
|TAI|International Atomic Time|
|TCB|Barycentric Coordinate Time|
|TDB|Barycentric Dynamical Time|
|TCG|Geocentric Coordinate Time|
|TT|Terrestrial Time|
|UT1|Universal Time|
|UTC|Coordinated Universal Time|



If MET or MRT is chosen as the TIME_SYSTEM, then the epoch of either the start of the mission for MRT, or of the event for MET, should either be given in a comment in the message or provided in an ICD. The time system for the start of the mission or the event should also be provided in the comment or the ICD.  If these values are used for the TIME_SYSTEM, then the times given in the file denote a duration from the mission start or event.  However, for clarity, an ICD should be used to fully specify the interpretation of the times if these values are to be used.  The time format should only utilize three-digit days from the MET or MRT epoch, not months and days of the months. 

**3.2.3.3** Values for the REF_FRAME keyword should be selected from the following set: 

|**REF_FRAME Value**|**Meaning**|
|---|---|
|EME2000|Earth Mean Equator and Equinox of J2000|
|GCRF|Geocentric Celestial Reference Frame|
|GRC|Greenwich RotatingCoordinates|
|ICRF|International Celestial Reference Frame|
|ITRF2000|International Terrestrial Reference Frame 2000|
|ITRF-93|International Terrestrial Reference Frame 1993|
|ITRF-97|International Terrestrial Reference Frame 1997|
|MCI|Mars Centered Inertial|
|TDR|True of Date,Rotating|
|TEME|True Equator Mean Equinox(onlyused in OMMs)|
|TOD|True of Date|









## **3.2.4 OPM DATA** 

**3.2.4.1** Table 3-3 provides an overview of the six logical blocks in the OPM Data section (State Vector, Osculating Keplerian Elements, Spacecraft Parameters, Position/Velocity Covariance Matrix, Maneuver Parameters, and User-Defined Parameters), and specifies for each data item: 

   - a) the keyword to be used; 

   - b) a short description of the item; 

   - c) the units to be used; 

   - d) whether the item is Mandatory (M), Optional (O), or Conditional (C).  An ‘M’ denotes mandatory keywords that must be included in this section if that particular data section is included.  Conditional indicates that the item is mandatory if specified conditions are met (e.g., providing all covariance matrix elements if any are provided). 

- **3.2.4.2** Only those keywords shown in table 3-3 shall be used in OPM data. 

NOTE – Requirements relating to the keywords in table 3-3 appear after the table. 

**Table 3-3:  OPM Data** 

State Vector Components in the Specified Coordinate System<br>
|**Keyword**|**Description**|**Units**|**M/O/C**|
|---|---|---|---|
|COMMENT|(see 7.8 for formattingrules)||O|
|EPOCH|Epoch of state vector & optional Keplerian<br>elements(see 7.5.10 for formattingrules)||M|
|X|Position vector X-component|km|M|
|Y|Position vector Y-component|km|M|
|Z|Position vector Z-component|km|M|
|X_DOT|Velocityvector X-component|km/s|M|
|Y_DOT|Velocityvector Y-component|km/s|M|
|ZDOT|Velocity vector Z-component|km/s|M|

Osculating Keplerian Elements in the Specified Reference Frame(none or allparameters of this block must begiven)
|**Keyword**|**Description**|**Units**|**M/O/C**|
|---|---|---|---|
|COMMENT|(see 7.8 for formattingrules)||O|
|SEMI_MAJOR_AXIS|Semi-major axis|km|C|
|ECCENTRICITY|Eccentricity||C|
|INCLINATION|Inclination|deg|C|
|RA_OF_ASC_NODE|Right ascension of ascendingnode|deg|C|
|ARG_OF_PERICENTER|Argument ofpericenter|deg|C|
|TRUE_ANOMALY or<br>MEAN_ANOMALY|True anomaly or mean anomaly|deg|C|
|GM|Gravitational Coefficient (Gravitational<br>Constant × Central Mass)|km**3/s**2|C|

Spacecraft Parameters(if maneuver is specified,then mass must beprovided)
|**Keyword**|**Description**|**Units**|**M/O/C**|
|---|---|---|---|
|COMMENT|(see 7.8 for formattingrules)||O|
|MASS<br>|Spacecraft mass|kg|C|
|SOLAR_RAD_AREA<br>|Solar Radiation Pressure Area(AR)|m**2|O|
|SOLAR_RAD_COEFF<br>|Solar Radiation Pressure Coefficient(CR)||O|
|DRAG_AREA<br>|DragArea(AD)|m**2|O|
|DRAG_COEFF<br>|Drag Coefficient (CD)||O|

Position/Velocity Covariance Matrix (6x6 Lower Triangular Form. None or all parameters of the matrix must be given. COV_REF_FRAME may be omitted if it is the same as REF_FRAME.)
|**Keyword**|**Description**|**Units**|**M/O/C**|
|---|---|---|---|
|COMMENT<br>|(see 7.8 for formattingrules)||O|
|COV_REF_FRAME<br>|Reference frame in which the covariance data are<br>given.  Select from the accepted set of values<br>indicated in 3.2.4.11.||C|
|CX_X<br>|Covariance matrix[1,1]|km**2|C|
|CY_X<br>|Covariance matrix[2,1]|km**2|C|
|CY_Y<br>|Covariance matrix[2,2]|km**2|C|
|CZ_X<br>|Covariance matrix[3,1]|km**2|C|
|CZ_Y<br>|Covariance matrix[3,2]|km**2|C|
|CZ_Z<br>|Covariance matrix[3,3]|km**2|C|
|CX_DOT_X<br>|Covariance matrix[4,1]|km**2/s|C|
|CX_DOT_Y<br>|Covariance matrix[4,2]|km**2/s|C|
|CX_DOT_Z<br>|Covariance matrix[4,3]|km**2/s|C|
|CX_DOT_X_DOT<br>|Covariance matrix[4,4]|km**2/s**2|C|
|CY_DOT_X<br>|Covariance matrix[5,1]|km**2/s|C|
|CY_DOT_Y<br>|Covariance matrix[5,2]|km**2/s|C|
|CY_DOT_Z<br>|Covariance matrix[5,3]|km**2/s|C|
|CY_DOT_X_DOT<br>|Covariance matrix[5,4]|km**2/s**2|C|
|CY_DOT_Y_DOT<br>|Covariance matrix[5,5]|km**2/s**2|C|
|CZ_DOT_X<br>|Covariance matrix[6,1]|km**2/s|C|
|CZ_DOT_Y<br>|Covariance matrix[6,2]|km**2/s|C|
|CZ_DOT_Z<br>|Covariance matrix[6,3]|km**2/s|C|
|CZ_DOT_X_DOT<br>|Covariance matrix[6,4]|km**2/s**2|C|
|CZ_DOT_Y_DOT<br>|Covariance matrix[6,5]|km**2/s**2|C|
|CZ_DOT_Z_DOT<br>|Covariance matrix [6,6]|km**2/s**2|C|

Maneuver Parameters(Repeat for each maneuver)
|**Keyword**|**Description**|**Units**|**M/O/C**|
|---|---|---|---|
|COMMENT<br>|(see 7.8 for formattingrules)||O|
|MAN_EPOCH_IGNITION<br>Epoch of ignition(see 7.5.10 for formattingrules)||O|
|MAN_DURATION<br>|Maneuver duration(If = 0,impulsive maneuver)|s|O|
|MAN_DELTA_MASS<br>|Mass change duringmaneuver(value is < 0)|kg|O|
|MAN_REF_FRAME<br>|Reference frame in which the velocity increment<br>vector data are given.  The user must select from<br>the accepted set of values indicated in 3.2.4.11.||O|
|MAN_DV_1<br>|1<sup>st</sup>component of the velocityincrement|km/s|O|
|MAN_DV_2<br>|2<sup>nd</sup>component of the velocityincrement|km/s|O|
|MAN_DV_3<br>|3<sup>rd</sup>component of the velocityincrement|km/s|O|









User-Defined Parameters (all parameters in this section must be described in an ICD)
|**Keyword**|**Description**|**Units**|**M/O/C**|
|---|---|---|---|
|USER_DEFINED_x<br>|User-defined parameter, where ‘x’ is replaced by a<br>variable-length user-specified character string.<br>Any number of user-defined parameters may be<br>included, if necessary, to provide essential<br>information that cannot be conveyed in<br>COMMENT statements.  Example:<br>USER_DEFINED_EARTH_MODEL = WGS-84||O|



**3.2.4.3** All values except Maneuver Parameters in the OPM data are ‘at epoch’, that is, the value of the parameter at the time specified in the EPOCH keyword. 

**3.2.4.4** Table 3-3 is broken into six logical blocks, each of which has a descriptive heading. These descriptive headings shall not be included in an OPM, unless they appear in a properly formatted COMMENT statement. 

**3.2.4.5** If the solar radiation coefficient, CR, is set to zero, no solar radiation pressure shall be considered. 

NOTE – It is recommended that CR and solar radiation pressure area be provided for GEO spacecraft. 

**3.2.4.6** If the atmospheric drag coefficient, CD, is set to zero, no atmospheric drag shall be considered. 

NOTE – It is recommended that CD and drag area be provided for LEO spacecraft. 

**3.2.4.7** Parameters for thrust phases may be optionally given for the computation of the trajectory during or after maneuver execution (see reference [H1] for the simplified modeling of such maneuvers).  For impulsive maneuvers, MAN_DURATION must be set to zero. MAN_DELTA_MASS may be used for both finite and impulsive maneuvers; the value must be a negative number. 

**3.2.4.8** Multiple sets of maneuver parameters may appear.  For each maneuver, all the maneuver parameters shall be repeated in the order shown in table 3-3. 

**3.2.4.9** If the OPM contains a maneuver definition, then the Conditional elements of the Spacecraft Parameters section (designated with a ‘C’) must be included. 

**3.2.4.10** Values in the covariance matrix shall be expressed in the applicable reference frame (COV_REF_FRAME keyword) and shall be presented sequentially from upper left [1,1] to lower right [6,6], lower triangular form, row by row, left to right. Variance and covariance values shall be expressed in standard double precision as related in 7.5.  This logical block of the OPM may be useful for risk assessment and establishing maneuver and mission margins. The intent is to provide causal connections between output orbit data and both physical hypotheses and measurement uncertainties.  These causal relationships guide operators’ corrective actions and mitigations. 







**3.2.4.11** Values for the MAN_REF_FRAME and COV_REF_FRAME keyword may be selected from the following set: 

|**Reference Frame Value**|**Meaning**|
|---|---|
|RSW|Another name for ‘Radial, Transverse, Normal’|
|RTN|Radial, Transverse, Normal|
|TNW|A local orbital coordinate frame that has the x-axis along the<br>velocity vector, W along the orbital angular momentum vector,<br>and N completing the right-handed system|



**3.2.4.12** A section of User-Defined Parameters may be provided if necessary.  In principle, this provides flexibility, but also introduces complexity, non-standardization, potential ambiguity, and potential processing errors.  Accordingly, if used, the keywords and their meanings must be described in an ICD.  User-Defined Parameters, if included, should be used as sparingly as possible; their use is not encouraged. 





