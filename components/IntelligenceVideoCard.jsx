'use client';

export default function IntelligenceVideoCard({ title, source, videoUrl }) {
  
  const handleDownload = async () => {
    const response = await fetch(videoUrl);
    const blob = await response.blob();
    const url = window.URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `${source}_intelligence_clip.mp4`;
    document.body.appendChild(link);
    link.click();
    link.remove();
  };

  return (
    <div className="flex flex-col bg-slate-900 border border-slate-800 rounded-xl overflow-hidden w-full max-w-md">
      <video 
        src={videoUrl} 
        controls 
        className="w-full h-64 object-cover bg-black"
      />
      
      <div className="p-4 flex justify-between items-center">
        <div>
          <h3 className="text-white font-semibold truncate">{title}</h3>
          <span className="text-slate-400 text-sm uppercase tracking-wider">{source}</span>
        </div>
        
        <button 
          onClick={handleDownload}
          className="px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white rounded-lg transition-colors shadow-lg shadow-blue-900/20"
        >
          Download MP4
        </button>
      </div>
    </div>
  );
}
