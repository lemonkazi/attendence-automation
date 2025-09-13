import { useState, useEffect } from "react";
import { Clock } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";

const LiveClock = () => {
  const [time, setTime] = useState<string>("");
  const [date, setDate] = useState<string>("");

  useEffect(() => {
    const updateClock = () => {
      const now = new Date();
      
      // Format time for Asia/Dhaka timezone
      const timeFormatter = new Intl.DateTimeFormat('en-US', {
        timeZone: 'Asia/Dhaka',
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit',
        hour12: true
      });
      
      // Format date for Asia/Dhaka timezone
      const dateFormatter = new Intl.DateTimeFormat('en-US', {
        timeZone: 'Asia/Dhaka',
        year: 'numeric',
        month: 'long',
        day: 'numeric',
        weekday: 'long'
      });
      
      setTime(timeFormatter.format(now));
      setDate(dateFormatter.format(now));
    };

    updateClock();
    const interval = setInterval(updateClock, 1000);

    return () => clearInterval(interval);
  }, []);

  return (
    <Card className="bg-hero-gradient border-0 text-white shadow-elegant">
      <CardContent className="p-2 text-center">
        <div className="flex items-center justify-center gap-2 mb-2">
          <Clock className="w-6 h-6" />
          <span className="text-sm font-medium opacity-90">Dhaka Time</span>
        </div>
        <div className="text-5xl md:text-6xl font-bold mb-1 font-mono tracking-wider">
          {time}
        </div>
        <div className="text-lg font-medium opacity-90">
          {date}
        </div>
      </CardContent>
    </Card>
  );
};

export default LiveClock;