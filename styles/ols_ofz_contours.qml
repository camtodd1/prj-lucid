<!DOCTYPE qgis PUBLIC 'http://mrcc.com/qgis.dtd' 'SYSTEM'>
<qgis version="3.40.5-Bratislava" styleCategories="Symbology|Labeling|CustomProperties" labelsEnabled="1">
  <renderer-v2 type="singleSymbol" symbollevels="0" referencescale="-1" forceraster="0" enableorderby="0">
    <symbols>
      <symbol name="0" type="line" alpha="1" clip_to_extent="1" force_rhr="0" is_animated="0" frame_rate="10">
        <data_defined_properties>
          <Option type="Map"><Option name="name" value="" type="QString"/><Option name="properties"/><Option name="type" value="collection" type="QString"/></Option>
        </data_defined_properties>
        <layer class="SimpleLine" enabled="1" locked="0" pass="0">
          <Option type="Map">
            <Option name="line_color" value="238,154,21,255,rgb:0.93333333333333335,0.60392156862745094,0.08235294117647059,1" type="QString"/>
            <Option name="line_style" value="solid" type="QString"/>
            <Option name="line_width" value="0.35" type="QString"/>
            <Option name="line_width_unit" value="MM" type="QString"/>
            <Option name="capstyle" value="square" type="QString"/>
            <Option name="joinstyle" value="bevel" type="QString"/>
            <Option name="offset" value="0" type="QString"/>
            <Option name="offset_unit" value="MM" type="QString"/>
            <Option name="use_custom_dash" value="0" type="QString"/>
            <Option name="draw_inside_polygon" value="0" type="QString"/>
          </Option>
          <data_defined_properties>
            <Option type="Map"><Option name="name" value="" type="QString"/><Option name="properties"/><Option name="type" value="collection" type="QString"/></Option>
          </data_defined_properties>
        </layer>
      </symbol>
    </symbols>
  </renderer-v2>
  <labeling type="simple">
    <settings>
      <text-style fieldName="CASE WHEN round(&quot;contour_elev_am&quot; * 2) / 2 = floor(round(&quot;contour_elev_am&quot; * 2) / 2) THEN format_number(round(&quot;contour_elev_am&quot; * 2) / 2, 0) ELSE format_number(round(&quot;contour_elev_am&quot; * 2) / 2, 1) END" isExpression="1" fontFamily="Helvetica" namedStyle="Regular" fontSize="10" fontSizeUnit="Point" fontWeight="50" textColor="80,55,15,255" textOpacity="1" previewBkgrdColor="255,255,255,255">
        <text-buffer bufferDraw="1" bufferSize="1" bufferSizeUnits="MM" bufferColor="255,238,204,255" bufferOpacity="0.8" bufferNoFill="1" bufferJoinStyle="128"/>
      </text-style>
      <text-format formatNumbers="0" decimals="3"/>
      <placement placement="2" layerType="LineGeometry" placementFlags="9" dist="0" repeatDistance="0" preserveRotation="1" overlapHandling="PreventOverlap"/>
      <rendering drawLabels="1" obstacle="1" obstacleFactor="1" maxNumLabels="2000" scaleVisibility="0"/>
    </settings>
  </labeling>
  <customproperties>
    <Option type="Map">
      <Option name="embeddedWidgets/count" value="0" type="int"/>
      <Option name="safeguarding_style_key" value="OLS OFZ Contour" type="QString"/>
      <Option name="variableNames"/>
      <Option name="variableValues"/>
    </Option>
  </customproperties>
</qgis>
