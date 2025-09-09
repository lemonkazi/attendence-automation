import { useState } from "react";
import { LogIn, LogOut, User, Calendar } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { useToast } from "@/hooks/use-toast";
import LiveClock from "./LiveClock";

const AttendanceSystem = () => {
  const [selectedEmployee, setSelectedEmployee] = useState<string>("");
  const [isLoading, setIsLoading] = useState<{ checkin: boolean; checkout: boolean }>({
    checkin: false,
    checkout: false
  });
  const { toast } = useToast();

  const employees = [
    "Abdullah Al Mamun",
    "Md. Nazmul Hasan", 
    "Md. Majharul Anwar"
  ];

  const getCurrentTime = () => {
    return new Intl.DateTimeFormat('en-US', {
      timeZone: 'Asia/Dhaka',
      hour: '2-digit',
      minute: '2-digit',
      hour12: true
    }).format(new Date());
  };

  const getTodayDate = () => {
    const now = new Date();
    const dhaka = new Intl.DateTimeFormat('en-US', {
      timeZone: 'Asia/Dhaka',
      month: 'numeric',
      day: 'numeric',
      year: 'numeric'
    }).format(now);
    return dhaka.replace(/(\d+)\/(\d+)\/(\d+)/, '$1/$2/$3'); // Format as M/D/YYYY
  };

  const handleAttendance = async (action: 'checkin' | 'checkout') => {
    if (!selectedEmployee) {
      toast({
        title: "Select Employee",
        description: "Please select an employee first",
        variant: "destructive"
      });
      return;
    }

    setIsLoading(prev => ({ ...prev, [action]: true }));

    try {
      const apiUrl = import.meta.env.VITE_API_URL || '/api';
      const response = await fetch(`${apiUrl}/attendance`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          employee: selectedEmployee,
          action: action,
          date: getTodayDate(),
          time: getCurrentTime()
        })
      });
      

      if (response.ok) {
        const actionText = action === 'checkin' ? 'checked-in' : 'checked-out';
        toast({
          variant: "success",
          title: "Success!",
          description: `${selectedEmployee} ${actionText} at ${getCurrentTime()}`,
        });
      } else {
        throw new Error('Failed to update attendance');
      }
    } catch (error) {
      toast({
        title: "Error",
        description: "Failed to update attendance. Please try again.",
        variant: "destructive"
      });
    } finally {
      setIsLoading(prev => ({ ...prev, [action]: false }));
    }
  };

  return (
    <div className="min-h-screen bg-background p-4">
      <div className="max-w-4xl mx-auto space-y-6">
        {/* Header */}
        <div className="text-center">
          <h1 className="text-4xl font-bold mb-2 bg-text-gradient bg-clip-text text-transparent">
            Employee Attendance System
          </h1>
          <p className="text-muted-foreground">
            Track employee check-ins and check-outs with real-time updates
          </p>
        </div>

        {/* Live Clock */}
        <LiveClock />

        {/* Attendance Form */}
        <Card className="shadow-card">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <User className="w-5 h-5" />
              Record Attendance
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-6">
            {/* Employee Selection */}
            <div className="space-y-2">
              <label className="text-sm font-medium">Select Employee</label>
              <Select value={selectedEmployee} onValueChange={setSelectedEmployee}>
                <SelectTrigger className="w-full">
                  <SelectValue placeholder="Choose an employee..." />
                </SelectTrigger>
                <SelectContent className="z-50 bg-background border shadow-lg">
                  {employees.map((employee) => (
                    <SelectItem key={employee} value={employee}>
                      {employee}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            {/* Current Date Display */}
            <div className="flex items-center gap-2 p-3 bg-secondary/50 rounded-lg">
              <Calendar className="w-4 h-4 text-muted-foreground" />
              <span className="text-sm">
                Recording for: <span className="font-medium">{getTodayDate()}</span>
              </span>
            </div>

            {/* Action Buttons */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <Button
                onClick={() => handleAttendance('checkin')}
                disabled={!selectedEmployee || isLoading.checkin}
                size="lg"
                className="h-16 text-lg"
              >
                <LogIn className="w-5 h-5 mr-2" />
                {isLoading.checkin ? "Processing..." : "Check In"}
              </Button>
              
              <Button
                onClick={() => handleAttendance('checkout')}
                disabled={!selectedEmployee || isLoading.checkout}
                variant="outline"
                size="lg"
                className="h-16 text-lg"
              >
                <LogOut className="w-5 h-5 mr-2" />
                {isLoading.checkout ? "Processing..." : "Check Out"}
              </Button>
            </div>

            {/* Instructions */}
            <div className="text-sm text-muted-foreground bg-muted/30 p-4 rounded-lg">
              <p className="font-medium mb-2">Instructions:</p>
              <ul className="space-y-1 list-disc list-inside">
                <li>Select an employee from the dropdown</li>
                <li>Click "Check In" when starting work</li>
                <li>Click "Check Out" when ending work</li>
                <li>Hours and overtime will be calculated automatically</li>
              </ul>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
};

export default AttendanceSystem;