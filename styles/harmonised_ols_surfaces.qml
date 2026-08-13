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
      <symbol name="0" type="fill" alpha="1"><layer class="SimpleFill"><Option type="Map"><Option name="color" value="244,171,160,90" type="QString"/><Option name="outline_color" value="166,83,75,255" type="QString"/><Option name="outline_width" value="0.35" type="QString"/><Option name="outline_width_unit" value="MM" type="QString"/></Option></layer></symbol>
      <symbol name="1" type="fill" alpha="1"><layer class="SimpleFill"><Option type="Map"><Option name="color" value="245,209,184,96" type="QString"/><Option name="outline_color" value="154,111,83,255" type="QString"/><Option name="outline_width" value="0.35" type="QString"/><Option name="outline_width_unit" value="MM" type="QString"/></Option></layer></symbol>
      <symbol name="2" type="fill" alpha="1"><layer class="SimpleFill"><Option type="Map"><Option name="color" value="249,243,222,92" type="QString"/><Option name="outline_color" value="156,139,94,255" type="QString"/><Option name="outline_width" value="0.30" type="QString"/><Option name="outline_width_unit" value="MM" type="QString"/></Option></layer></symbol>
      <symbol name="3" type="fill" alpha="1"><layer class="SimpleFill"><Option type="Map"><Option name="color" value="231,213,169,92" type="QString"/><Option name="outline_color" value="145,121,67,255" type="QString"/><Option name="outline_width" value="0.30" type="QString"/><Option name="outline_width_unit" value="MM" type="QString"/></Option></layer></symbol>
      <symbol name="4" type="fill" alpha="1"><layer class="SimpleFill"><Option type="Map"><Option name="color" value="96,100,114,74" type="QString"/><Option name="outline_color" value="53,56,66,255" type="QString"/><Option name="outline_width" value="0.40" type="QString"/><Option name="outline_width_unit" value="MM" type="QString"/></Option></layer></symbol>
      <symbol name="5" type="fill" alpha="1"><layer class="SimpleFill"><Option type="Map"><Option name="color" value="195,240,230,90" type="QString"/><Option name="outline_color" value="66,132,117,255" type="QString"/><Option name="outline_width" value="0.35" type="QString"/><Option name="outline_width_unit" value="MM" type="QString"/></Option></layer></symbol>
      <symbol name="6" type="fill" alpha="1"><layer class="SimpleFill"><Option type="Map"><Option name="color" value="182,216,223,80" type="QString"/><Option name="outline_color" value="75,116,126,255" type="QString"/><Option name="outline_width" value="0.30" type="QString"/><Option name="outline_width_unit" value="MM" type="QString"/></Option></layer></symbol>
      <symbol name="7" type="fill" alpha="1"><layer class="SimpleFill"><Option type="Map"><Option name="color" value="143,181,192,72" type="QString"/><Option name="outline_color" value="70,105,116,255" type="QString"/><Option name="outline_width" value="0.30" type="QString"/><Option name="outline_width_unit" value="MM" type="QString"/></Option></layer></symbol>
      <symbol name="8" type="fill" alpha="1"><layer class="SimpleFill"><Option type="Map"><Option name="color" value="154,158,170,60" type="QString"/><Option name="outline_color" value="82,86,99,255" type="QString"/><Option name="outline_width" value="0.30" type="QString"/><Option name="outline_width_unit" value="MM" type="QString"/></Option></layer></symbol>
    </symbols>
  </renderer-v2>
</qgis>
