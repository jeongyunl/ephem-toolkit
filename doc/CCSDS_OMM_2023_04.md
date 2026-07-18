
# **4 ORBIT MEAN-ELEMENTS MESSAGE** 

## **4.1 GENERAL** 

**4.1.1** Orbit information may be exchanged between two participants by sending an orbital state based on mean Keplerian elements (see reference [H1]) for a specified epoch using an OMM.  The message recipient must use appropriate orbit propagator algorithms to correctly propagate the OMM state to compute the orbit at other desired epochs. 

**4.1.2** The OMM is intended to allow replication of the data content of an existing TLE in a CCSDS standard format, but the message can also accommodate other implementations of mean elements.  All essential fields of the ‘de facto standard’ TLE are included in the OMM in a style that is consistent with that of the other ODMs (i.e., the OPM and OEM).  From the fields in the OMM, it is possible to generate a TLE (see reference [H2]).  Programs that convert OMMs to TLEs must be aware of the structural requirements of the TLE, including the checksum algorithm and the formatting requirements for the values in the TLE.  The checksum and formatting requirements of the TLE do not apply to the values in an OMM. 

**4.1.3** If participants wish to exchange osculating element information, then the OPM or the OCM should be the selected message type.  (See sections 3 and 6.) 

- **4.1.4** The use of the OMM is best applicable under the following conditions: 

   - a) an orbit propagator consistent with the models used to develop the orbit data should be run at the receiver’s site; 

   - b) the receiver’s modeling of gravitational forces, solar radiation pressure, atmospheric drag, etc. (see reference [H1]), should fulfill accuracy requirements established between the exchange partners. 

- **4.1.5** The OMM shall be a plain text file consisting of orbit data for a single object. 

- NOTE – A sequence of OMMs for either a single object or for multiple objects can be aggregated into a single NDM XML file as described in 8.12 and shown in annex G. 

**4.1.6** The OMM file-naming scheme should be mutually agreed upon between message exchange partners. 

**4.1.7** The method of exchanging OMMs should be mutually agreed upon between message exchange partners. 

## NOTES 

- 1 Detailed syntax rules for the OMM are specified in section 7. 

- 2 Example OMMs and associated supplementary (non-normative) information are provided in annex G. 



## **4.2 OMM CONTENT/STRUCTURE** 

## **4.2.1 GENERAL** 

The OMM shall be represented as a combination of the following: 

- a) a header; 

- b) metadata (data about data); 

- c) data; and 

- d) optional comments (explanatory information). 

## **4.2.2 OMM HEADER** 

- **4.2.2.1** Table 4-1 specifies for each header item: 

   - a) the keyword to be used; 

   - b) a short description of the item; 

   - c) examples of allowed values; and 

   - d) whether the item is Mandatory (M), Optional (O), or Conditional (C).  An ‘M’ denotes mandatory keywords that must be included in this section if that data section is included.  Conditional indicates that the item is mandatory if specified conditions are met (e.g., providing all covariance matrix elements if any are provided). 

- **4.2.2.2** Only those keywords shown in table 4-1 shall be used in an OMM header. 



## **Table 4-1:  OMM Header** 

|**Keyword**|**Description**|**Examples of Values**|**M/O/C**|
|---|---|---|---|
|`CCSDS_OMM_VERS`|Format version in the form of ‘x.y’, where ‘y’<br>is incremented for corrections and minor<br>changes, and ‘x’ is incremented for major<br>changes.|`3.0`|M|
|`COMMENT`|Comments (allowed in the OMM Header only<br>immediately after the OMM version number).<br>(See 7.8 for formatting rules.)|<br> <br>`This is a comment`|O|
|`CLASSIFICATION`|User-defined free-text message<br>classification/caveats of this OMM.  It is<br>recommended that selected values be pre-<br>coordinated between exchanging entities by<br>mutual agreement.|`SBU`<br>`'Operator-proprietary`<br>`data; secondary`<br>`distribution not`<br>`permitted'`|O|
|`CREATION_DATE`|File creation date/time in UTC. (For format<br>specification, see 7.5.10.)|`2001-11-06T11:17:33`<br>`2002-204T15:56:23Z`|M|
|`ORIGINATOR`|Creating agency or operator.  Select from the<br>accepted set of values indicated in annex B,<br>subsection B1 from the ‘Abbreviation’ column<br>(when present), or the ‘Name’ column when an<br>Abbreviation column is not populated.  If<br>desired organization is not listed there, follow<br>procedures to request that originator be added<br>to SANA registry.|`CNES, ESOC, GSFC,`<br>`GSOC, JPL, JAXA,`<br>`INTELSAT, USAF,`<br>`INMARSAT`|M|
|`MESSAGE_ID`|ID that uniquely identifies a message from a<br>given originator.  The format and content of<br>the message identifier value are at the<br>discretion of the originator.|`OMM 201113719185`<br>`ABC-12_34`|`O`|



## **4.2.3 OMM METADATA** 

## **4.2.3.1** Table 4-2 specifies for each metadata item: 

   - a) the keyword to be used; 

   - b) a short description of the item; 

   - c) examples of allowed values; and 

   - d) whether the item is Mandatory (M), Optional (O), or Conditional (C).  Conditional indicates that the item is mandatory if specified conditions are met (e.g., providing _all_ covariance matrix elements if _any_ are provided). 

- **4.2.3.2** Only those keywords shown in 4-2 shall be used in OMM metadata. 



NOTE – For some keywords (OBJECT_NAME and OBJECT_ID), there are no definitive lists of authorized values maintained by a control authority; references [3] and [11] and the organizations provided on the SANA Registry (annex B, subsection B1) are the best known sources for authorized values to date. 

**Table 4-2:  OMM Metadata** 

|**Keyword**|**Description**|**Examples of Values**|**M/O/C**|
|---|---|---|---|
|`COMMENT`|Comments (allowed at the beginning of the<br>OMM Metadata).(See 7.8 for formattingrules.)|`This is a comment`|O|
|`OBJECT_NAME`|Spacecraft name for which mean element orbit<br>state data is provided.  While there is no CCSDS-<br>based restriction on the value for this keyword, it<br>is recommended to use names from the UN<br>Office of Outer Space Affairs designator index<br>(reference [3], which include Object name and<br>international designator of the participant).  If<br>OBJECT_NAME is not listed in reference [3] or<br>the content is either unknown or cannot be<br>disclosed, the value should be set to<br>UNKNOWN.|`TelKom 2`<br>`Spaceway 2`<br>`INMARSAT 4-F2`<br>`UNKNOWN`|`M`|
|`OBJECT_ID`|Object identifier of the object for which mean<br>element orbit state data is provided.  While there<br>is no CCSDS-based restriction on the value for<br>this keyword, it is recommended to use the<br>international spacecraft designator as published<br>in the UN Office of Outer Space Affairs<br>designator index (reference [3]).  Recommended<br>values have the format YYYY-NNNP{PP},<br>where:<br>YYYY = Year of launch.<br>NNN<br>= Three-digit serial number of launch<br>in year YYYY (with leading zeros).<br>P{PP} = At least one capital letter for the<br>identification of the part brought into<br>space by the launch.<br>If the asset is not listed in reference [3], the UN<br>Office of Outer Space Affairs designator index<br>format is not used, or the content is either<br>unknown or cannot be disclosed, the value<br>should be set to UNKNOWN.|<br> <br> <br> <br> <br>`2005-046A`<br>`2005-046B`<br>`2003-022A`<br>`UNKNOWN`|M|
|`CENTER_NAME`|Origin of the OMM reference frame, which<br>shall be a natural solar system body (planets,<br>asteroids, comets, and natural satellites),<br>including any planet barycenter or the solar<br>system barycenter.  Natural bodies shall be<br>selected from the accepted set of values<br>indicated in annex B,subsection B2.|`EARTH`<br>`MARS`<br>`MOON`|M|





|**Keyword**|**Description**|**Examples of Values**|**M/O/C**|
|---|---|---|---|
|`REF_FRAME`|Reference frame in which the Keplerian element<br>data are given. Use of values other than those in<br>3.2.3.3 should be documented in an ICD.<br>NOTE – NORAD Two Line Element Sets and<br>corresponding Simplified General<br>Perturbations (SGP) orbit propagator<br>ephemeris outputs are explicitly<br>defined to be in the True Equator<br>Mean Equinox of Date (TEME of<br>Date) reference frame. Therefore,<br>TEME of date shall be used for<br>OMMs based on NORAD Two Line<br>Element sets, rather than the almost<br>imperceptibly different TEME of<br>Epoch (see reference [H2] or [H3] for<br>further details).|<br>`ICRF`<br>`ITRF2000`<br>`EME2000`<br>`TEME`|M|
|`REF_FRAME_EPOCH`|Epoch of reference frame, if not intrinsic to the<br>definition of the reference frame.  (See 7.5.10<br>for formattingrules.)|`2001-11-06T11:17:33`<br>`2002-204T15:56:23Z`|<br>C|
|`TIME_SYSTEM`|Time system used for Keplerian elements and<br>covariance data.  Use of values other than those<br>in 3.2.3.2 should be documented in an ICD.|`UTC`|M|
|`MEAN_ELEMENT_THEORY`|Description of the Mean Element Theory.<br>Indicates the proper method to employ to<br>propagate the state.|`SGP`<br>`SGP4`<br>`SGP4-XP`<br>`DSST`<br>`USM`|M|



## **4.2.4 OMM DATA** 

**4.2.4.1** Table 4-3 provides an overview of the five logical blocks in the OMM Data section (Mean Keplerian Elements, Spacecraft Parameters, TLE Related Parameters, Position/Velocity Covariance Matrix, and User-Defined Parameters), and specifies for each data item: 

   - a) the keyword to be used; 

   - b) a short description of the item; 

   - c) the units to be used; and 

   - d) whether the item is Mandatory (M), Optional (O), or Conditional (C).  Conditional indicates that the item is mandatory if specified conditions are met (e.g., providing _all_ covariance matrix elements if _any_ are provided). 

- **4.2.4.2** Only those keywords shown in table 4-3 shall be used in OMM data. 

NOTE – Requirements relating to the keywords in table 4-3 appear after the table. 



## **Table 4-3:  OMM Data** 

|**Keyword**|**Description**|**Units**|**M/O/C**|
|---|---|---|---|
|Mean Keplerian Elements in the|Specified Reference Frame|||
|`COMMENT`|(see 7.8 for formattingrules)||O|
|`EPOCH`|Epoch of Mean Keplerian elements (see 7.5.10 for<br>formattingrules)||M|
|`SEMI_MAJOR_AXIS or`<br>`MEAN_MOTION`|Semi-major axis in kilometers (preferred), or, if<br>MEAN_ELEMENT_THEORY = SGP/SGP4, the<br>Keplerian Mean motion in revolutionsper day|km<br>rev/day|M|
|`ECCENTRICITY`|Eccentricity||M|
|`INCLINATION`|Inclination|deg|M|
|`RA_OF_ASC_NODE`|Right ascension of ascendingnode|deg|M|
|`ARG_OF_PERICENTER`|Argument ofpericenter|deg|M|
|`MEAN_ANOMALY`|Mean anomaly|deg|M|
|`GM`|Gravitational Coefficient (Gravitational Constant × Central<br>Mass)|km**3/s**2|O|
|Spacecraft Parameters||||
|`COMMENT`|(see 7.8 for formattingrules.)||O|
|`MASS`|Spacecraft Mass|kg|O|
|`SOLAR_RAD_AREA`|Solar Radiation Pressure Area(AR)|m**2|O|
|`SOLAR_RAD_COEFF`|Solar Radiation Pressure Coefficient(CR)||O|
|`DRAG_AREA`|DragArea(AD)|m**2|O|
|`DRAG_COEFF`|Drag Coefficient (CD)||O|
|TLE Related Parameters | (This selection is only required if MEAN_ELEMENT_THEORY = SGP/SGP4)|||
|`COMMENT`|(see 7.8 for formattingrules.)||O|
|`EPHEMERIS_TYPE`|Default value = 0.(See 4.2.4.7.)||O|
|`CLASSIFICATION_TYPE`|Default value = U.(See 4.2.4.7.)||O|
|`NORAD_CAT_ID`|NORAD Catalog Number (‘Satellite Number’) an integer<br>of up to nine digits.  This keyword is only required if<br>MEAN_ELEMENT_THEORY = SGP/SGP4.||O|
|`ELEMENT_SET_NO`|Element set number for this satellite.  Normally<br>incremented sequentially but may be out of sync if it is<br>generated from a backup source.  Used to distinguish<br>different TLEs, and therefore only meaningful if TLE-<br>based data is being exchanged (i.e.,<br>MEAN_ELEMENT_THEORY = SGP/SGP4).||O|
|`REV_AT_EPOCH`|Revolution Number||O|
|`BSTAR or BTERM`|Drag-like ballistic coefficient, required for SGP4 and SGP4-<br>XP mean element models:<br>MEAN_ELEMENT_THEORY = SGP4 (BSTAR = drag<br>parameter for SGP4).<br>MEAN_ELEMENT_THEORY = SGP4-XP (BTERM<br>ballistic coefficient_C_D_A_/_m_, where_C_D= drag coefficient,_A_=<br>average cross-sectional area,_m_= mass.  Example values for<br>BTERM = 0.02 (rocket body), 0.0015 (payload); average<br>value spanning20,00 catalogobjects = 0.0286.|BSTAR:<br>1/[Earth radii]<br>BTERM:<br>𝑘<sup>2</sup><br>𝑘𝑘<br>�|C|
|`MEAN_MOTION_DOT`|First Time Derivative of the Mean Motion (i.e., a drag<br>term, required when MEAN_ELEMENT_THEORY =<br>SGP or PPT3).(See 4.2.4.7 for important details).|rev/day**2|C|





|**Keyword**|**Description**|**Units**|**M/O/C**|
|---|---|---|---|
|`MEAN_MOTION_DDOT or`<br>`AGOM`|MEAN_ELEMENT_THEORY = SGP or PPT3: Second<br>Time Derivative of Mean Motion (i.e., a drag term).  (See<br>4.2.4.7 for important details).<br>MEAN_ELEMENT_THEORY = SGP4-XP:  Solar radiation<br>pressure coefficient<sup>𝐴𝐴</sup>𝑘<br>�, where 𝐴= reflectivity, _A_=average cross-sectional area, _m_= mass.  Example values<br>AGOM = 0.01 (rocket body) and 0.001 (payload); average<br>value spanning 20,00 catalog objects = 0.0143 m2/kg.|MEAN_MOTION_DDOT:<br>rev/day**3<br><br>AGOM: m<sup>2</sup>/kg<br>|C|
|Position/Velocity Covariance Matrix| (6x6 Lower Triangular Form. **None or all parameters of the matrix must be given**<br>COV_REF_FRAME maybe omitted if it is the same as the REF_FRAME.)||
|COMMENT|(see 7.8 for formattingrules.)||O|
|COV_REF_FRAME|Reference frame in which the covariance data are given.<br>Select from the accepted set of values indicated in<br>3.2.4.11.||C|
|CX_X|Covariance matrix[1,1]|km**2|C|
|CY_X|Covariance matrix[2,1]|km**2|C|
|CY_Y|Covariance matrix[2,2]|km**2|C|
|CZ_X|Covariance matrix[3,1]|km**2|C|
|CZ_Y|Covariance matrix[3,2]|km**2|C|
|CZ_Z|Covariance matrix[3,3]|km**2|C|
|CX_DOT_X|Covariance matrix[4,1]|km**2/s|C|
|CX_DOT_Y|Covariance matrix[4,2]|km**2/s|C|
|CX_DOT_Z|Covariance matrix[4,3]|km**2/s|C|
|CX_DOT_X_DOT|Covariance matrix[4,4]|km**2/s**2|C|
|CY_DOT_X|Covariance matrix[5,1]|km**2/s|C|
|CY_DOT_Y|Covariance matrix[5,2]|km**2/s|C|
|CY_DOT_Z|Covariance matrix[5,3]|km**2/s|C|
|CY_DOT_X_DOT|Covariance matrix[5,4]|km**2/s**2|C|
|CY_DOT_Y_DOT|Covariance matrix[5,5]|km**2/s**2|C|
|CZ_DOT_X|Covariance matrix[6,1]|km**2/s|C|
|CZ_DOT_Y|Covariance matrix[6,2]|km**2/s|C|
|CZ_DOT_Z|Covariance matrix[6,3]|km**2/s|C|
|CZ_DOT_X_DOT|Covariance matrix[6,4]|km**2/s**2|C|
|CZ_DOT_Y_DOT|Covariance matrix[6,5]|km**2/s**2|C|
|CZ_DOT_Z_DOT|Covariance matrix [6,6]|km**2/s**2|C|
|User-Defined Parameters(allp|arameters in this section must be described in an ICD).|||
|`USER_DEFINED_x`|User-defined parameter, where ‘x’ is replaced by a<br>variable length user specified character string.  Any<br>number of user-defined parameters may be included, if<br>necessary, to provide essential information that cannot be<br>conveyed in COMMENT statements.  Example:<br>USER_DEFINED_EARTH_MODEL = WGS-84||O|



**4.2.4.3** All values in the OMM are ‘at epoch’, that is, the value of the parameter at the time specified in the EPOCH keyword. 

**4.2.4.4** Table 4-3 is broken into five logical blocks, each of which has a descriptive heading.  These descriptive headings shall not be included in an OMM, unless they appear in a properly formatted COMMENT statement. 

**4.2.4.5** Values in the covariance matrix shall be expressed in the applicable reference frame (COV_REF_FRAME keyword if used, or REF_FRAME keyword if not), and shall be presented sequentially from upper left [1,1] to lower right [6,6], lower triangular form, row by row left to right. Variance and covariance values shall be expressed in standard double precision as related in 7.5.  This logical block of the OMM may be useful for risk assessment and establishing maneuver and mission margins. 

**4.2.4.6** For operations in Earth orbit with a TLE-based OMM, some special conventions must be observed, as follows: 

- The value associated with the CENTER_NAME keyword shall be ‘EARTH’. 

- The value associated with the REF_FRAME keyword shall be ‘TEME’. 

- The value associated with the TIME_SYSTEM keyword shall be ‘UTC’. 

- The format of the OBJECT_NAME and OBJECT_ID keywords shall be that of the UN Office of Outer Space Affairs designator index (reference [3]). 

- The MEAN_MOTION keyword must be used instead of SEMI_MAJOR_AXIS. 

**4.2.4.7** For those who wish to use the OMM to represent a TLE, there are several considerations that apply with respect to precision of angle representation, use of certain fields by the propagator, reference frame, etc.  Some sources suggest the following coding for the CLASSIFICATION_TYPE keyword: U=unclassified, S=secret. Some sources suggest the coding for the EPHEMERIS_TYPE keyword as follows: 

0 = SGP<br>
2 = SGP4<br>
3 = PPT3<br>
4 = SGP4-XP <br>
6 = Special Perturbations 

## NOTES 

- 1 References [H2] and [H3] can be consulted for additional information. 

- 2 If the source of MEAN_MOTION_DOT and MEAN_MOTION_DDOT is a TLE or if these values are intended to be used as a TLE, then these values need to be divided by 2 and 6 respectively to reflect the SGP theory Taylor Series expansion terms. 

**4.2.4.8** Maneuvers are not accommodated in the OMM.  Users of the OMM who wish to model maneuvers may use several OMM files to describe the orbit at applicable epochs. 

**4.2.4.9** NORAD Two Line Element Sets are implicitly in a TEME of Date reference frame, which is ill-defined in international standard or convention. TEME may be used only for OMMs based on NORAD Two Line Element sets, and in no other circumstances.  There are subtle differences between TEME of Epoch and TEME of Date (see references [H2] and [H3]).  The effect is very small relative to TLE accuracy.  The preferred option is TEME of Date.  Users should specify in the ICD if their assumption is TEME of Epoch. 

**4.2.4.10** A section of User-Defined Parameters may be provided if necessary.  In principle, this provides flexibility, but also introduces complexity, non-standardization, potential ambiguity, and potential processing errors.  Accordingly, if used, the keywords and their meanings must be described in an ICD.  User-Defined Parameters, if included, should be used as sparingly as possible; their use is not encouraged. 

