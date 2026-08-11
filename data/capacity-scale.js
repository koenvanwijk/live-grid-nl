(()=>{
  /**
   * Shared visual capacity scale for map symbols.
   * Diameter is proportional to sqrt(MW), so symbol AREA is approximately
   * proportional to installed/transfer capacity. The same MW therefore gets
   * the same diameter for generation, renewables, storage and interconnectors.
   */
  window.capacityDiameter=function capacityDiameter(mw){
    const value=Math.max(0,Number(mw)||0);
    return Math.round(Math.max(18,Math.min(72,12+1.25*Math.sqrt(value))));
  };
})();
