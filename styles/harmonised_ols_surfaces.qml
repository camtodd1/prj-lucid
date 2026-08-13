<!DOCTYPE qgis PUBLIC 'http://mrcc.com/qgis.dtd' 'SYSTEM'>
<qgis version="3.40.5-Bratislava" styleCategories="Symbology">
  <renderer-v2 type="RuleRenderer" symbollevels="0" enableorderby="0" forceraster="0">
    <rules key="harmonised-ols-rules">
      <rule key="approach" label="Approach" symbol="0" filter="replace(replace(lower(&quot;surface&quot;), ' ', '_'), '-', '_') = 'approach'"/>
      <rule key="inner-approach" label="Inner Approach" symbol="1" filter="replace(replace(lower(&quot;surface&quot;), ' ', '_'), '-', '_') = 'inner_approach'"/>
      <rule key="transitional" label="Transitional" symbol="2" filter="replace(replace(lower(&quot;surface&quot;), ' ', '_'), '-', '_') = 'transitional'"/>
      <rule key="inner-transitional" label="Inner Transitional" symbol="3" filter="replace(replace(lower(&quot;surface&quot;), ' ', '_'), '-', '_') = 'inner_transitional'"/>
      <rule key="balked" label="Baulked Landing" symbol="4" filter="replace(replace(lower(&quot;surface&quot;), ' ', '_'), '-', '_') IN ('balked_landing', 'baulked_landing')"/>
      <rule key="takeoff" label="Take-off Climb" symbol="5" filter="replace(replace(lower(&quot;surface&quot;), ' ', '_'), '-', '_') IN ('take_off_climb', 'tocs')"/>
      <rule key="inner-horizontal" label="Inner Horizontal" symbol="6" filter="replace(replace(lower(&quot;surface&quot;), ' ', '_'), '-', '_') IN ('inner_horizontal', 'ihs', 'horizontal')"/>
      <rule key="conical" label="Conical" symbol="7" filter="replace(replace(lower(&quot;surface&quot;), ' ', '_'), '-', '_') LIKE 'conical%'"/>
      <rule key="outer-horizontal" label="Outer Horizontal" symbol="8" filter="replace(replace(lower(&quot;surface&quot;), ' ', '_'), '-', '_') IN ('outer_horizontal', 'ohs')"/>
    </rules>
    <symbols>
      <symbol name="0" type="fill" alpha="1"><layer class="SimpleFill"><Option type="Map"><Option name="color" value="231,111,81,76" type="QString"/><Option name="outline_color" value="174,68,45,255" type="QString"/><Option name="outline_width" value="0.35" type="QString"/><Option name="outline_width_unit" value="MM" type="QString"/></Option></layer></symbol>
      <symbol name="1" type="fill" alpha="1"><layer class="SimpleFill"><Option type="Map"><Option name="color" value="244,162,97,84" type="QString"/><Option name="outline_color" value="190,103,36,255" type="QString"/><Option name="outline_width" value="0.35" type="QString"/><Option name="outline_width_unit" value="MM" type="QString"/></Option></layer></symbol>
      <symbol name="2" type="fill" alpha="1"><layer class="SimpleFill"><Option type="Map"><Option name="color" value="233,196,106,68" type="QString"/><Option name="outline_color" value="170,132,37,255" type="QString"/><Option name="outline_width" value="0.30" type="QString"/><Option name="outline_width_unit" value="MM" type="QString"/></Option></layer></symbol>
      <symbol name="3" type="fill" alpha="1"><layer class="SimpleFill"><Option type="Map"><Option name="color" value="213,93,146,72" type="QString"/><Option name="outline_color" value="148,49,92,255" type="QString"/><Option name="outline_width" value="0.30" type="QString"/><Option name="outline_width_unit" value="MM" type="QString"/></Option></layer></symbol>
      <symbol name="4" type="fill" alpha="1"><layer class="SimpleFill"><Option type="Map"><Option name="color" value="196,69,54,82" type="QString"/><Option name="outline_color" value="137,41,29,255" type="QString"/><Option name="outline_width" value="0.40" type="QString"/><Option name="outline_width_unit" value="MM" type="QString"/></Option></layer></symbol>
      <symbol name="5" type="fill" alpha="1"><layer class="SimpleFill"><Option type="Map"><Option name="color" value="0,180,216,65" type="QString"/><Option name="outline_color" value="0,113,138,255" type="QString"/><Option name="outline_width" value="0.35" type="QString"/><Option name="outline_width_unit" value="MM" type="QString"/></Option></layer></symbol>
      <symbol name="6" type="fill" alpha="1"><layer class="SimpleFill"><Option type="Map"><Option name="color" value="87,117,144,56" type="QString"/><Option name="outline_color" value="48,72,94,255" type="QString"/><Option name="outline_width" value="0.30" type="QString"/><Option name="outline_width_unit" value="MM" type="QString"/></Option></layer></symbol>
      <symbol name="7" type="fill" alpha="1"><layer class="SimpleFill"><Option type="Map"><Option name="color" value="67,128,161,55" type="QString"/><Option name="outline_color" value="36,78,101,255" type="QString"/><Option name="outline_width" value="0.30" type="QString"/><Option name="outline_width_unit" value="MM" type="QString"/></Option></layer></symbol>
      <symbol name="8" type="fill" alpha="1"><layer class="SimpleFill"><Option type="Map"><Option name="color" value="91,95,118,48" type="QString"/><Option name="outline_color" value="58,61,80,255" type="QString"/><Option name="outline_width" value="0.30" type="QString"/><Option name="outline_width_unit" value="MM" type="QString"/></Option></layer></symbol>
    </symbols>
  </renderer-v2>
</qgis>
