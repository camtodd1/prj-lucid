<!DOCTYPE qgis PUBLIC 'http://mrcc.com/qgis.dtd' 'SYSTEM'>
<qgis version="3.40.5-Bratislava" styleCategories="Symbology">
  <renderer-v2 type="RuleRenderer" symbollevels="0" enableorderby="0" forceraster="0">
    <rules key="harmonised-ols-contour-rules">
      <rule key="approach" label="Approach" symbol="0" filter="replace(replace(lower(&quot;surface&quot;), ' ', '_'), '-', '_') = 'approach'"/>
      <rule key="inner-approach" label="Inner Approach" symbol="1" filter="replace(replace(lower(&quot;surface&quot;), ' ', '_'), '-', '_') = 'inner_approach'"/>
      <rule key="transitional" label="Transitional" symbol="2" filter="replace(replace(lower(&quot;surface&quot;), ' ', '_'), '-', '_') = 'transitional'"/>
      <rule key="inner-transitional" label="Inner Transitional" symbol="3" filter="replace(replace(lower(&quot;surface&quot;), ' ', '_'), '-', '_') = 'inner_transitional'"/>
      <rule key="balked" label="Balked Landing" symbol="4" filter="replace(replace(lower(&quot;surface&quot;), ' ', '_'), '-', '_') IN ('balked_landing', 'baulked_landing')"/>
      <rule key="takeoff" label="Take-off Climb" symbol="5" filter="replace(replace(lower(&quot;surface&quot;), ' ', '_'), '-', '_') IN ('take_off_climb', 'tocs')"/>
      <rule key="inner-horizontal" label="Inner Horizontal" symbol="6" filter="replace(replace(lower(&quot;surface&quot;), ' ', '_'), '-', '_') IN ('inner_horizontal', 'ihs', 'horizontal')"/>
      <rule key="conical" label="Conical" symbol="7" filter="replace(replace(lower(&quot;surface&quot;), ' ', '_'), '-', '_') LIKE 'conical%'"/>
      <rule key="outer-horizontal" label="Outer Horizontal" symbol="8" filter="replace(replace(lower(&quot;surface&quot;), ' ', '_'), '-', '_') IN ('outer_horizontal', 'ohs')"/>
    </rules>
    <symbols>
      <symbol name="0" type="line"><layer class="SimpleLine"><Option type="Map"><Option name="line_color" value="174,68,45,255" type="QString"/><Option name="line_width" value="0.42" type="QString"/><Option name="line_width_unit" value="MM" type="QString"/></Option></layer></symbol>
      <symbol name="1" type="line"><layer class="SimpleLine"><Option type="Map"><Option name="line_color" value="190,103,36,255" type="QString"/><Option name="line_width" value="0.42" type="QString"/><Option name="line_width_unit" value="MM" type="QString"/></Option></layer></symbol>
      <symbol name="2" type="line"><layer class="SimpleLine"><Option type="Map"><Option name="line_color" value="170,132,37,255" type="QString"/><Option name="line_width" value="0.38" type="QString"/><Option name="line_width_unit" value="MM" type="QString"/></Option></layer></symbol>
      <symbol name="3" type="line"><layer class="SimpleLine"><Option type="Map"><Option name="line_color" value="148,49,92,255" type="QString"/><Option name="line_width" value="0.38" type="QString"/><Option name="line_width_unit" value="MM" type="QString"/></Option></layer></symbol>
      <symbol name="4" type="line"><layer class="SimpleLine"><Option type="Map"><Option name="line_color" value="137,41,29,255" type="QString"/><Option name="line_width" value="0.45" type="QString"/><Option name="line_width_unit" value="MM" type="QString"/></Option></layer></symbol>
      <symbol name="5" type="line"><layer class="SimpleLine"><Option type="Map"><Option name="line_color" value="0,113,138,255" type="QString"/><Option name="line_width" value="0.42" type="QString"/><Option name="line_width_unit" value="MM" type="QString"/></Option></layer></symbol>
      <symbol name="6" type="line"><layer class="SimpleLine"><Option type="Map"><Option name="line_color" value="48,72,94,255" type="QString"/><Option name="line_width" value="0.35" type="QString"/><Option name="line_width_unit" value="MM" type="QString"/></Option></layer></symbol>
      <symbol name="7" type="line"><layer class="SimpleLine"><Option type="Map"><Option name="line_color" value="36,78,101,255" type="QString"/><Option name="line_width" value="0.38" type="QString"/><Option name="line_width_unit" value="MM" type="QString"/></Option></layer></symbol>
      <symbol name="8" type="line"><layer class="SimpleLine"><Option type="Map"><Option name="line_color" value="58,61,80,255" type="QString"/><Option name="line_width" value="0.35" type="QString"/><Option name="line_width_unit" value="MM" type="QString"/></Option></layer></symbol>
    </symbols>
  </renderer-v2>
</qgis>
