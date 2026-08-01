<!DOCTYPE qgis PUBLIC 'http://mrcc.com/qgis.dtd' 'SYSTEM'>
<qgis version="3.40.5" labelsEnabled="1" simplifyDrawingHints="1" simplifyLocal="1" simplifyMaxScale="1" simplifyDrawingTol="1" simplifyAlgorithm="0" minScale="100000000" maxScale="0" readOnly="0" styleCategories="AllStyleCategories">
  <renderer-v2 type="singleSymbol" symbollevels="0" enableorderby="0" forceraster="0" referencescale="-1">
    <symbols>
      <symbol type="fill" name="0" alpha="1" clip_to_extent="1" force_rhr="0" is_animated="0" frame_rate="10">
        <layer class="SimpleFill" enabled="1" pass="0" locked="0" id="{b18d0c5b-a9e5-4a69-8f9c-2dcb8e7b1c6a}">
          <Option type="Map">
            <Option name="border_width_map_unit_scale" type="QString" value="3x:0,0,0,0,0,0"/>
            <Option name="color" type="QString" value="212,93,105,55,rgb:0.8313726,0.3647059,0.4117647,0.2156863"/>
            <Option name="joinstyle" type="QString" value="round"/>
            <Option name="offset" type="QString" value="0,0"/>
            <Option name="offset_map_unit_scale" type="QString" value="3x:0,0,0,0,0,0"/>
            <Option name="offset_unit" type="QString" value="MM"/>
            <Option name="outline_color" type="QString" value="159,45,61,255,rgb:0.6235294,0.1764706,0.2392157,1"/>
            <Option name="outline_style" type="QString" value="dash"/>
            <Option name="outline_width" type="QString" value="0.62"/>
            <Option name="outline_width_unit" type="QString" value="MM"/>
            <Option name="style" type="QString" value="solid"/>
          </Option>
        </layer>
      </symbol>
    </symbols>
    <rotation/>
    <sizescale/>
    <data-defined-properties>
      <Option type="Map">
        <Option name="name" type="QString" value=""/>
        <Option name="properties"/>
        <Option name="type" type="QString" value="collection"/>
      </Option>
    </data-defined-properties>
  </renderer-v2>
  <labeling type="simple">
    <settings>
      <text-style fontFamily="Arial" fontSize="9" fontSizeUnit="Point" fontWeight="600" textColor="159,45,61,255,rgb:0.6235294,0.1764706,0.2392157,1" fieldName="concat(&quot;zone_code&quot;, ' ', &quot;end_desig&quot;, '\nRWY ', &quot;rwy&quot;)" isExpression="1"/>
      <text-format/>
      <placement geometryGenerator="point_on_surface($geometry)" geometryGeneratorEnabled="1" geometryGeneratorType="PointGeometry" placement="1"/>
      <rendering scaleVisibility="1" maximumScale="1" minimumScale="100000000"/>
    </settings>
  </labeling>
</qgis>
