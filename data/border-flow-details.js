(()=>{
  const CAPACITY_MW={DE:4000,BE:1700,GB:1000,NO2:700,DK1:700};
  const COUNTRY_BY_NAME={'Duitsland':'DE','België':'BE','Groot-Brittannië':'GB','Noorwegen':'NO2','Denemarken':'DK1'};
  const color=u=>u>=.8?'#ff5964':u>=.5?'#ffca59':'#49eca0';
  const fmt=v=>Math.round(v).toLocaleString('nl-NL');

  function enhance(){
    const root=document.querySelector('#borderFlows');
    if(!root)return;
    for(const row of root.querySelectorAll('.flow-row')){
      if(row.dataset.enhanced==='1')continue;
      const name=row.querySelector('.country-name')?.textContent?.trim();
      const country=COUNTRY_BY_NAME[name];
      const cap=CAPACITY_MW[country];
      if(!cap)continue;
      const flowText=row.querySelector('strong')?.textContent||'0';
      const flow=Math.abs(Number(flowText.replace(/\./g,'').replace(',','.').replace(/[^0-9.-]/g,''))||0);
      const outbound=row.querySelector('.arrow')?.classList.contains('out');
      const u=Math.min(1,flow/cap),c=color(u);
      const detail=document.createElement('div');
      detail.className='border-flow-detail';
      detail.style.setProperty('--flow-color',c);
      detail.innerHTML=`<div class="border-capacity"><span>capaciteit</span><b>${fmt(cap)} MW</b><span>${Math.round(u*100)}%</span></div><div class="border-mini-flow ${outbound?'reverse':''}" aria-label="${outbound?'export':'import'} ${fmt(flow)} MW van ${fmt(cap)} MW capaciteit"><i></i><i></i><i></i><i></i></div>`;
      row.appendChild(detail);
      row.dataset.enhanced='1';
    }
  }

  const root=document.querySelector('#borderFlows');
  if(root)new MutationObserver(()=>requestAnimationFrame(enhance)).observe(root,{childList:true,subtree:true});
  enhance();
  setInterval(enhance,2000);
})();