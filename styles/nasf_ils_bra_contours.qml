<!DOCTYPE qgis PUBLIC 'http://mrcc.com/qgis.dtd' 'SYSTEM'>
<qgis version="4.0.2-Norrköping" styleCategories="AllStyleCategories" labelsEnabled="1">
  <renderer-v2 type="RuleRenderer" symbollevels="0" enableorderby="0" forceraster="0">
    <rules key="ils-bra-contour-rules">
      <rule key="primary" label="Primary contour" symbol="0" filter="&quot;contclass&quot; = 'primary'"/>
      <rule key="intermediate" label="Intermediate contour" symbol="1" filter="ELSE"/>
    </rules>
    <symbols>
      <symbol name="0" type="line" alpha="1"><layer class="SimpleLine" enabled="1"><Option type="Map"><Option name="line_color" value="89,61,145,255" type="QString"/><Option name="line_width" value="0.65" type="QString"/><Option name="line_width_unit" value="MM" type="QString"/><Option name="line_style" value="solid" type="QString"/></Option></layer></symbol>
      <symbol name="1" type="line" alpha="1"><layer class="SimpleLine" enabled="1"><Option type="Map"><Option name="line_color" value="137,112,181,190" type="QString"/><Option name="line_width" value="0.30" type="QString"/><Option name="line_width_unit" value="MM" type="QString"/><Option name="line_style" value="solid" type="QString"/></Option></layer></symbol>
    </symbols>
  </renderer-v2>
  <labeling type="simple">
    <settings calloutType="simple">
      <text-style fieldName="CASE WHEN round(&quot;contagl_m&quot; * 2) / 2 = floor(round(&quot;contagl_m&quot; * 2) / 2) THEN format_number(round(&quot;contagl_m&quot; * 2) / 2, 0) ELSE format_number(round(&quot;contagl_m&quot; * 2) / 2, 1) END" isExpression="1" fontFamily="Helvetica" fontSize="10" fontSizeUnit="Point" textColor="70,48,116,255" fontWeight="50">
        <text-buffer bufferDraw="1" bufferSize="1" bufferSizeUnits="MM" bufferColor="255,255,255,220"/>
      </text-style>
      <placement placement="2" lineAnchorType="0" lineAnchorPercent="0.5" lineAnchorTextPoint="FollowPlacement" preserveRotation="1" maxCurvedCharAngleIn="25" maxCurvedCharAngleOut="-25" priority="5" overlapHandling="PreventOverlap"/>
      <rendering drawLabels="1" upsidedownLabels="0" obstacle="1" obstacleFactor="1"/>
    </settings>
  </labeling>
</qgis>
