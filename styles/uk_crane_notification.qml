<!DOCTYPE qgis PUBLIC 'http://mrcc.com/qgis.dtd' 'SYSTEM'>
<qgis version="3.40.5" labelsEnabled="1" simplifyDrawingHints="1" simplifyLocal="1" simplifyMaxScale="1" simplifyDrawingTol="1" simplifyAlgorithm="0" minScale="100000000" maxScale="0" readOnly="0" styleCategories="AllStyleCategories">
  <renderer-v2 type="singleSymbol" symbollevels="0" enableorderby="0" forceraster="0" referencescale="-1">
    <symbols>
      <symbol type="fill" name="0" alpha="1" clip_to_extent="1" force_rhr="0" is_animated="0" frame_rate="10">
        <layer class="SimpleFill" enabled="1" pass="0" locked="0" id="{6aee560f-197a-4d5b-8d8d-dccf7f44cd37}">
          <Option type="Map">
            <Option name="border_width_map_unit_scale" type="QString" value="3x:0,0,0,0,0,0"/>
            <Option name="color" type="QString" value="225,89,137,32,rgb:0.8823529,0.3490196,0.5372549,0.1254902"/>
            <Option name="joinstyle" type="QString" value="round"/>
            <Option name="offset" type="QString" value="0,0"/>
            <Option name="offset_map_unit_scale" type="QString" value="3x:0,0,0,0,0,0"/>
            <Option name="offset_unit" type="QString" value="MM"/>
            <Option name="outline_color" type="QString" value="161,64,98,255,rgb:0.6302434,0.2493019,0.3837796,1"/>
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
      <text-style fontFamily="Arial" fontSize="9" fontSizeUnit="Point" fontWeight="600" textColor="161,64,98,255,rgb:0.6302434,0.2493019,0.3837796,1" fieldName="concat(&quot;zone&quot;, '\n', format_number(&quot;radius_km&quot;, 0), ' km')" isExpression="1"/>
      <text-format/>
      <placement geometryGenerator="point_on_surface($geometry)" geometryGeneratorEnabled="1" geometryGeneratorType="PointGeometry" placement="1"/>
      <rendering scaleVisibility="1" maximumScale="1" minimumScale="100000000"/>
    </settings>
  </labeling>
</qgis>
